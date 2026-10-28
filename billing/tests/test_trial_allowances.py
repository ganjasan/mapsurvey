"""Tests for the `pro-trial-allowances` capability.

Spec: openspec/changes/pro-trial-allowances/specs/pro-trial-allowances/spec.md
(after archive: openspec/specs/pro-trial-allowances/spec.md). One module per capability -- see #273.
"""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from survey.models import Membership

from .. import entitlements as ents
from .. import events as ev
from .. import trial
from ..models import STATUS_REFUNDED, EntitlementGrant, GrantAllowance
from .helpers import PPG_SETTINGS, make_org, make_sub

OFFER = {'api': 500, 'unbranded': 1, 'pro_help': 1}


def _expire(grant):
    EntitlementGrant.objects.filter(pk=grant.pk).update(expires_at=timezone.now() - timedelta(seconds=1))


def _spend(grant, feature, used):
    GrantAllowance.objects.filter(grant=grant, feature=feature).update(used=used)


@override_settings(**PPG_SETTINGS)
class ClaimTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.url = f'/org/{self.org.slug}/billing/trial/'

    def test_claim_creates_grant_and_allowances(self):
        """
        GIVEN a Free workspace and the registry offer api 500 / unbranded 1 / pro_help 1 for 90 days
        WHEN the owner claims the trial
        THEN one trial grant expires 90 days after it starts, with three allowances at used 0 and the registry limits
        """
        grant = trial.claim(self.org, self.owner)
        self.assertEqual(grant.kind, 'trial')
        self.assertEqual(grant.claimed_by, self.owner)
        self.assertEqual(grant.expires_at - grant.starts_at, timedelta(days=90))
        self.assertEqual({a.feature: (a.limit, a.used) for a in grant.allowances.all()},
                         {k: (v, 0) for k, v in OFFER.items()})

    def test_owner_claims_through_the_endpoint_and_returns_to_next(self):
        """
        GIVEN the owner of a Free workspace without a grant
        WHEN they POST to the claim endpoint with a local next path
        THEN a grant exists, trial_claimed is emitted once on the owner, and the response redirects to next
        """
        self.client.login(username='bill_owner', password='pass')
        with mock.patch.object(ev, 'emit') as emit:
            r = self.client.post(self.url, {'next': '/editor/'})
        self.assertRedirects(r, '/editor/', fetch_redirect_response=False)
        self.assertTrue(EntitlementGrant.objects.filter(organization=self.org).exists())
        emit.assert_called_once_with(ev.TRIAL_CLAIMED, self.owner.pk, {'org_id': self.org.pk})

    def test_external_next_is_ignored(self):
        """
        GIVEN the claim endpoint
        WHEN next points to another host
        THEN the response redirects to Plan & billing instead
        """
        self.client.login(username='bill_owner', password='pass')
        r = self.client.post(self.url, {'next': 'https://evil.example/'})
        self.assertRedirects(r, f'/org/{self.org.slug}/billing/', fetch_redirect_response=False)

    def test_get_is_refused(self):
        """
        GIVEN the claim endpoint
        WHEN it is requested with GET
        THEN the response is 405 and no grant exists
        """
        self.client.login(username='bill_owner', password='pass')
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_admin_cannot_claim(self):
        """
        GIVEN an admin member of a Free workspace
        WHEN they POST to the claim endpoint
        THEN the response is 403 and no grant exists
        """
        admin = User.objects.create_user(username='bill_admin', password='pass')
        Membership.objects.create(user=admin, organization=self.org, role='admin')
        self.client.login(username='bill_admin', password='pass')
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_pro_workspace_is_refused(self):
        """
        GIVEN a workspace with an active subscription
        WHEN its owner claims
        THEN no grant is created
        """
        make_sub(self.org)
        with self.assertRaises(trial.TrialRefused) as cm:
            trial.claim(self.org, self.owner)
        self.assertEqual(cm.exception.reason, trial.REFUSED_PRO)
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_one_trial_per_user_across_workspaces(self):
        """
        GIVEN a user who claimed a trial in workspace A and owns workspace B
        WHEN they claim in B through the endpoint
        THEN no grant is created for B and Plan & billing says the trial was used in A
        """
        trial.claim(self.org, self.owner)
        other, _ = make_org('Second Org', owner_username='second_owner')
        Membership.objects.create(user=self.owner, organization=other, role='owner')
        self.client.login(username='bill_owner', password='pass')
        r = self.client.post(f'/org/{other.slug}/billing/trial/', follow=True)
        self.assertFalse(EntitlementGrant.objects.filter(organization=other).exists())
        self.assertContains(r, f'You already used your Pro trial in {self.org.name}')

    def test_one_trial_per_workspace(self):
        """
        GIVEN a workspace whose first owner claimed a trial
        WHEN a second owner who never claimed one claims for the same workspace
        THEN the claim is refused as already used
        """
        trial.claim(self.org, self.owner)
        second = User.objects.create_user(username='co_owner', password='pass')
        Membership.objects.create(user=second, organization=self.org, role='owner')
        with self.assertRaises(trial.TrialRefused) as cm:
            trial.claim(self.org, second)
        self.assertEqual(cm.exception.reason, trial.REFUSED_ORG_USED)

    def test_database_backstops_one_trial_per_user(self):
        """
        GIVEN a user holding a trial grant
        WHEN a second trial row for the same user is inserted directly
        THEN the database refuses it
        """
        trial.claim(self.org, self.owner)
        other, _ = make_org('Third Org', owner_username='third_owner')
        now = timezone.now()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EntitlementGrant.objects.create(organization=other, kind='trial', claimed_by=self.owner,
                                            starts_at=now, expires_at=now + timedelta(days=1))

    def test_registration_creates_no_trial(self):
        """
        GIVEN a freshly registered owner and workspace
        WHEN nothing is clicked
        THEN no grant exists
        """
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_not_offered_hides_the_control_and_404s(self):
        """
        GIVEN an empty TRIAL_ALLOWANCES
        WHEN the owner of a Free workspace opens Plan & billing and POSTs to the claim endpoint
        THEN no "Try Pro" control renders and the endpoint answers 404
        """
        self.client.login(username='bill_owner', password='pass')
        with mock.patch.object(trial, 'TRIAL_ALLOWANCES', {}):
            page = self.client.get(f'/org/{self.org.slug}/billing/')
            self.assertNotContains(page, '/billing/trial/')
            self.assertNotContains(page, 'id="pro-trial"')
            self.assertEqual(self.client.post(self.url).status_code, 404)

    def test_existing_grant_keeps_its_limits(self):
        """
        GIVEN a grant claimed with api 500
        WHEN the registry later says api 200
        THEN the grant's allowance still reads limit 500
        """
        grant = trial.claim(self.org, self.owner)
        with mock.patch.object(trial, 'TRIAL_ALLOWANCES', {'api': 200}):
            self.assertEqual(grant.allowances.get(feature='api').limit, 500)


@override_settings(**PPG_SETTINGS)
class MayTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.grant = trial.claim(self.org, self.owner)

    def _ent(self):
        ents.forget(self.org)
        return ents.for_organization(self.org)

    def test_free_with_live_trial(self):
        """
        GIVEN a Free workspace with a live trial, api used 10 of 500
        WHEN its entitlements are read
        THEN has('api') is false, may('api') is true and 490 remain
        """
        _spend(self.grant, 'api', 10)
        e = self._ent()
        self.assertFalse(e.has('api'))
        self.assertTrue(e.may('api'))
        self.assertEqual(e.allowances['api'].remaining, 490)
        self.assertEqual(e.trial.pk, self.grant.pk)

    def test_one_feature_exhausted(self):
        """
        GIVEN the trial's pro_help allowance is spent
        WHEN entitlements are read
        THEN may('pro_help') is false and may('api') stays true
        """
        _spend(self.grant, 'pro_help', 1)
        e = self._ent()
        self.assertFalse(e.may('pro_help'))
        self.assertTrue(e.may('api'))

    def test_expired(self):
        """
        GIVEN expires_at has passed
        WHEN entitlements are read
        THEN may is false for every feature and trial is None
        """
        _expire(self.grant)
        e = self._ent()
        self.assertIsNone(e.trial)
        self.assertFalse(any(e.may(k) for k in OFFER))

    def test_revoked(self):
        """
        GIVEN staff set revoked_at on the grant
        WHEN entitlements are read
        THEN the trial no longer counts
        """
        EntitlementGrant.objects.filter(pk=self.grant.pk).update(revoked_at=timezone.now())
        self.assertFalse(self._ent().may('api'))

    def test_lapse_resumes_the_trial(self):
        """
        GIVEN a workspace that claimed a trial, then bought Pro, then lapsed within the 90 days
        WHEN entitlements are read after the lapse
        THEN may('api') answers from the trial's untouched 500 calls
        """
        sub = make_sub(self.org)
        self.assertTrue(self._ent().has('api'))
        sub.status = STATUS_REFUNDED
        sub.save()
        e = self._ent()
        self.assertFalse(e.has('api'))
        self.assertTrue(e.may('api'))
        self.assertEqual(e.allowances['api'].remaining, 500)


@override_settings(**PPG_SETTINGS)
class ConsumeTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.grant = trial.claim(self.org, self.owner)

    def _used(self, feature='api'):
        return self.grant.allowances.get(feature=feature).used

    def test_last_use_is_won_once_and_exhaustion_emitted_once(self):
        """
        GIVEN one api call left
        WHEN consume runs twice
        THEN the first returns True and reaches the limit, the second returns False, and trial_exhausted is emitted once
        """
        _spend(self.grant, 'api', 499)
        with mock.patch.object(ev, 'emit') as emit:
            self.assertTrue(trial.consume(self.org, 'api', actor=self.owner))
            self.assertFalse(trial.consume(self.org, 'api', actor=self.owner))
        self.assertEqual(self._used(), 500)
        emit.assert_called_once_with(ev.TRIAL_EXHAUSTED, self.owner.pk, {'org_id': self.org.pk, 'feature': 'api'})

    def test_stale_cache_cannot_overspend(self):
        """
        GIVEN two requests that loaded the entitlements while one call was left
        WHEN both consume
        THEN exactly one wins: the guard is in the UPDATE, not in the cached remainder
        """
        _spend(self.grant, 'api', 499)
        org_a = type(self.org).objects.get(pk=self.org.pk)
        org_b = type(self.org).objects.get(pk=self.org.pk)
        ents.for_organization(org_a)
        ents.for_organization(org_b)
        results = [trial.consume(org_a, 'api'), trial.consume(org_b, 'api')]
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(self._used(), 500)

    def test_pro_never_consumes(self):
        """
        GIVEN a Pro workspace that also holds a live trial
        WHEN the API is used
        THEN consume allows it and the allowance is unchanged
        """
        make_sub(self.org)
        self.assertTrue(trial.consume(self.org, 'api'))
        self.assertEqual(self._used(), 0)

    def test_no_trial_consumes_nothing(self):
        """
        GIVEN a Free workspace without a grant
        WHEN consume runs
        THEN it returns False
        """
        other, _ = make_org('Plain Org', owner_username='plain_owner')
        self.assertFalse(trial.consume(other, 'api'))

    def test_refusal_names_the_state(self):
        """
        GIVEN workspaces with no trial, a live but spent trial, and an expired trial
        WHEN refusal() is asked
        THEN it answers none, exhausted and expired
        """
        other, _ = make_org('Plain Org', owner_username='plain_owner')
        self.assertEqual(trial.refusal(other), 'none')
        _spend(self.grant, 'api', 500)
        self.assertEqual(trial.refusal(self.org), 'exhausted')
        _expire(self.grant)
        self.assertEqual(trial.refusal(self.org), 'expired')


@override_settings(**PPG_SETTINGS)
class BillingPageTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.url = f'/org/{self.org.slug}/billing/'
        self.client.login(username='bill_owner', password='pass')

    def test_available_offers_the_button(self):
        """
        GIVEN a Free workspace without a grant
        WHEN the owner opens Plan & billing
        THEN the trial block lists the allowances and the "Try Pro" form posts to the claim endpoint
        """
        r = self.client.get(self.url)
        self.assertContains(r, 'data-trial-state="available"')
        self.assertContains(r, f'action="/org/{self.org.slug}/billing/trial/"')
        self.assertContains(r, '<span class="trial-tile__figure">500</span><span class="trial-tile__label">API and MCP calls</span>', html=False)
        self.assertContains(r, 'A check-up of your survey before launch')

    def test_admin_sees_the_offer_without_a_button(self):
        """
        GIVEN an admin of a Free workspace without a grant
        WHEN they open Plan & billing
        THEN the block says the owner can start it and renders no claim form
        """
        admin = User.objects.create_user(username='bill_admin', password='pass')
        Membership.objects.create(user=admin, organization=self.org, role='admin')
        self.client.login(username='bill_admin', password='pass')
        r = self.client.get(self.url)
        self.assertContains(r, 'The workspace owner can start it')
        self.assertNotContains(r, '/billing/trial/')

    def test_live_shows_used_of_limit_and_end_date(self):
        """
        GIVEN a live trial with api used 120 of 500
        WHEN the owner opens Plan & billing
        THEN the page shows "120 of 500 used", the other allowances and the end date
        """
        grant = trial.claim(self.org, self.owner)
        _spend(grant, 'api', 120)
        r = self.client.get(self.url)
        self.assertContains(r, 'API and MCP calls: 120 of 500 used')
        self.assertContains(r, 'Surveys without the Mapsurvey badge: 0 of 1 used')
        self.assertContains(r, 'The trial ends on')

    def test_expired(self):
        """
        GIVEN a trial past its expires_at
        WHEN the owner opens Plan & billing
        THEN the block says when it ended and offers no claim
        """
        _expire(trial.claim(self.org, self.owner))
        r = self.client.get(self.url)
        self.assertContains(r, 'data-trial-state="expired"')
        self.assertNotContains(r, '/billing/trial/')

    def test_exhausted(self):
        """
        GIVEN a live trial with every allowance spent
        WHEN the owner opens Plan & billing
        THEN the block says the trial used everything
        """
        grant = trial.claim(self.org, self.owner)
        GrantAllowance.objects.filter(grant=grant).update(used=500)
        GrantAllowance.objects.filter(grant=grant).exclude(feature='api').update(used=1)
        self.assertContains(self.client.get(self.url), 'data-trial-state="exhausted"')

    def test_used_elsewhere(self):
        """
        GIVEN the owner claimed their trial in another workspace
        WHEN they open this workspace's Plan & billing
        THEN the block names the other workspace and offers no claim
        """
        other, _ = make_org('Other Org', owner_username='other_owner')
        Membership.objects.create(user=self.owner, organization=other, role='owner')
        trial.claim(other, self.owner)
        r = self.client.get(self.url)
        self.assertContains(r, 'You already used your Pro trial in Other Org')
        self.assertNotContains(r, '/billing/trial/')

    def test_pro_has_no_trial_block(self):
        """
        GIVEN a Pro workspace
        WHEN the owner opens Plan & billing
        THEN no trial block renders
        """
        make_sub(self.org)
        self.assertNotContains(self.client.get(self.url), 'id="pro-trial"')


@override_settings(**PPG_SETTINGS)
class RefusalPageTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def _page(self, user, feature='pro_help'):
        from ..gates import feature_required
        request = RequestFactory().get('/somewhere/?x=1')
        request.user = user
        ents.forget(self.org)
        return feature_required(request, self.org, feature).content.decode()

    def test_owner_gets_try_pro_with_next(self):
        """
        GIVEN the owner of a Free workspace without a grant
        WHEN a Pro feature is refused
        THEN the page offers "Try Pro" posting to the claim endpoint with next set to the refused page
        """
        html = self._page(self.owner)
        self.assertIn('data-trial-state="available"', html)
        self.assertIn('name="next" value="/somewhere/?x=1"', html)

    def test_feature_used_up_sentence(self):
        """
        GIVEN a live trial whose pro_help allowance is spent
        WHEN pro_help is refused
        THEN the page says the trial's allowance for this is used
        """
        grant = trial.claim(self.org, self.owner)
        _spend(grant, 'pro_help', 1)
        self.assertIn('data-trial-state="feature_used"', self._page(self.owner))

    def test_expired_sentence(self):
        """
        GIVEN an expired trial
        WHEN a feature is refused
        THEN the page says when the trial ended
        """
        _expire(trial.claim(self.org, self.owner))
        self.assertIn('data-trial-state="expired"', self._page(self.owner))


@override_settings(**PPG_SETTINGS)
class TrialHeroTest(TestCase):
    """The dashboard hero for the trial: `trial_available` + `has_surveys`, and its no-argument link."""

    HERO_ID = '2026-10-28-try-pro'
    A_DAY_LATER = date(2026, 10, 29)

    def setUp(self):
        from survey.models import SurveyHeader
        self.org, self.owner = make_org()
        SurveyHeader.objects.create(organization=self.org, name='park_plan')

    def _hero(self, user, org):
        from survey import changelog
        from survey.changelog_audience import Audience
        hero = changelog.hero_for('', Audience(user, org), today=self.A_DAY_LATER)
        return hero.id if hero else None

    def test_owner_of_free_workspace_with_surveys_gets_the_hero(self):
        """
        GIVEN the owner of a Free workspace with a survey and no trial
        WHEN the pending hero is asked for
        THEN it is the Pro trial hero, linking to the no-argument try-pro address
        """
        from survey import changelog
        self.assertEqual(self._hero(self.owner, self.org), self.HERO_ID)
        entry = next(e for e in changelog.entries() if e.id == self.HERO_ID)
        self.assertEqual(entry.link, 'billing_try_pro')

    def test_not_for_members_pro_or_claimed(self):
        """
        GIVEN an admin of that workspace, then the owner after claiming, then a Pro workspace's owner
        WHEN the trial hero's audience is checked
        THEN none of them gets it
        """
        from survey.changelog_audience import trial_available
        admin = User.objects.create_user(username='hero_admin', password='pass')
        Membership.objects.create(user=admin, organization=self.org, role='admin')
        self.assertFalse(trial_available(admin, self.org))
        pro, pro_owner = make_org('Pro Org', owner_username='pro_owner')
        make_sub(pro)
        self.assertFalse(trial_available(pro_owner, pro))
        trial.claim(self.org, self.owner)
        ents.forget(self.org)
        self.assertFalse(trial_available(self.owner, self.org))

    def test_not_after_a_trial_elsewhere(self):
        """
        GIVEN an owner who used their trial in another workspace
        WHEN the audience is checked for a second Free workspace they own
        THEN the hero is not for them
        """
        from survey.changelog_audience import trial_available
        other, _ = make_org('Other Org', owner_username='other_owner')
        Membership.objects.create(user=self.owner, organization=other, role='owner')
        trial.claim(other, self.owner)
        self.assertFalse(trial_available(self.owner, self.org))

    def test_try_pro_lands_on_the_trial_block(self):
        """
        GIVEN a signed-in owner whose active workspace is set
        WHEN they follow the hero's link
        THEN they land on that workspace's Plan & billing at the trial block
        """
        self.client.login(username='bill_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        r = self.client.get('/billing/try-pro/?from=hero')
        self.assertRedirects(r, f'/org/{self.org.slug}/billing/#pro-trial', fetch_redirect_response=False)
