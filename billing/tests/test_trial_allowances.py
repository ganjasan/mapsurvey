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

OFFER = {'api': 500, 'unbranded': 1, 'pro_help': 1, 'operator_entry': None}
CAPPED = {k: v for k, v in OFFER.items() if v is not None}


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
        GIVEN a Free workspace and the registry offer api 500 / unbranded 1 / pro_help 1 / operator_entry uncapped
        WHEN the owner claims the trial
        THEN one trial grant expires 90 days after it starts, triggered by "click", with four allowances at used 0
             and the registry limits (operator_entry with none)
        """
        grant = trial.claim(self.org, self.owner)
        self.assertEqual(grant.kind, 'trial')
        self.assertEqual(grant.claimed_by, self.owner)
        self.assertEqual((grant.trigger, grant.started_by), ('click', self.owner))
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
        emit.assert_called_once_with(ev.TRIAL_CLAIMED, self.owner.pk, {
            'org_id': self.org.pk, 'trigger': 'click', 'auto': False, 'started_by_owner': True})

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
        THEN the block says it starts with the first Pro use and renders no claim form
        """
        admin = User.objects.create_user(username='bill_admin', password='pass')
        Membership.objects.create(user=admin, organization=self.org, role='admin')
        self.client.login(username='bill_admin', password='pass')
        r = self.client.get(self.url)
        self.assertContains(r, 'It starts with the first Pro use')
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
        GIVEN a live trial whose every allowance is capped (claimed before paper entry joined) and spent
        WHEN the owner opens Plan & billing
        THEN the block says the trial used everything
        """
        grant = trial.claim(self.org, self.owner)
        GrantAllowance.objects.filter(grant=grant, limit__isnull=True).delete()
        GrantAllowance.objects.filter(grant=grant).update(used=500)
        GrantAllowance.objects.filter(grant=grant).exclude(feature='api').update(used=1)
        self.assertContains(self.client.get(self.url), 'data-trial-state="exhausted"')

    def test_uncapped_allowance_keeps_the_trial_live(self):
        """
        GIVEN a live trial with every capped allowance spent and paper entry uncapped
        WHEN the owner opens Plan & billing
        THEN the trial reads live, and paper entry shows its count with no limit
        """
        grant = trial.claim(self.org, self.owner)
        for k, v in CAPPED.items():
            _spend(grant, k, v)
        _spend(grant, 'operator_entry', 42)
        r = self.client.get(self.url)
        self.assertContains(r, 'data-trial-state="live"')
        self.assertContains(r, 'no limit')

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


# --- change pro-trial-auto (#508): the trial starts itself on the first Pro use ---

def _editor_of(org, username='auto_editor'):
    user = User.objects.create_user(username=username, password='pass', email=f'{username}@example.test')
    Membership.objects.create(user=user, organization=org, role='editor')
    return user


class AutoStartTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.editor = _editor_of(self.org)

    def test_may_without_starting(self):
        """
        GIVEN a Free workspace that never had a trial, whose owner has not used theirs
        WHEN may() is asked for every trial feature
        THEN it is true for each, Entitlements.may stays false, and no grant exists
        """
        for key in OFFER:
            self.assertTrue(trial.may(self.org, key), key)
            self.assertFalse(ents.for_organization(self.org).may(key), key)
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_editor_use_starts_the_owners_trial(self):
        """
        GIVEN that workspace and its editor
        WHEN the editor makes the first api use
        THEN the owner's trial exists with started_by = editor and trigger "api", api reads 1 used, and the
             start is announced as auto
        """
        with mock.patch.object(ev, 'emit') as emit:
            self.assertTrue(trial.use(self.org, 'api', actor=self.editor))
        grant = EntitlementGrant.objects.get(organization=self.org)
        self.assertEqual((grant.claimed_by, grant.started_by, grant.trigger), (self.owner, self.editor, 'api'))
        self.assertEqual(grant.allowances.get(feature='api').used, 1)
        self.assertEqual(trial.started_here(self.org), grant)
        emit.assert_called_once_with(ev.TRIAL_CLAIMED, self.editor.pk, {
            'org_id': self.org.pk, 'trigger': 'api', 'auto': True, 'started_by_owner': False})

    def test_second_use_counts_against_the_same_grant(self):
        """
        GIVEN a trial started by a first use
        WHEN a second use of the same feature is made from a fresh instance of the workspace
        THEN no second grant exists and api reads 2 used
        """
        from survey.models import Organization
        trial.use(self.org, 'api', actor=self.editor)
        trial.use(Organization.objects.get(pk=self.org.pk), 'api', actor=self.editor)
        self.assertEqual(EntitlementGrant.objects.count(), 1)
        self.assertEqual(GrantAllowance.objects.get(feature='api').used, 2)

    def test_owner_who_used_their_trial_elsewhere(self):
        """
        GIVEN the workspace's only owner claimed a trial in another workspace
        WHEN an editor makes a Pro use here
        THEN may() is false, use() returns false and no grant is created here
        """
        from .helpers import trial_used_elsewhere
        trial_used_elsewhere(self.org)
        self.assertFalse(trial.may(self.org, 'unbranded'))
        self.assertFalse(trial.use(self.org, 'unbranded', actor=self.editor))
        self.assertFalse(EntitlementGrant.objects.filter(organization=self.org).exists())

    def test_two_owners_the_one_without_a_trial_gets_it(self):
        """
        GIVEN owner A (joined first, trial used elsewhere) and owner B (joined later, no trial)
        WHEN the first Pro use happens
        THEN the grant belongs to B
        """
        from .helpers import trial_used_elsewhere
        trial_used_elsewhere(self.org)
        b = User.objects.create_user(username='owner_b', password='pass')
        Membership.objects.create(user=b, organization=self.org, role='owner')
        trial.use(self.org, 'pro_help', actor=self.editor)
        self.assertEqual(EntitlementGrant.objects.get(organization=self.org).claimed_by, b)

    def test_pro_workspace_never_starts(self):
        """
        GIVEN a workspace with an active subscription
        WHEN the API is used
        THEN use() is true and no grant is created
        """
        make_sub(self.org)
        ents.forget(self.org)
        self.assertTrue(trial.use(self.org, 'api', actor=self.editor))
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_trial_not_offered_never_starts(self):
        """
        GIVEN TRIAL_ALLOWANCES is empty
        WHEN an editor makes a Pro use
        THEN may() and use() are false and no grant exists
        """
        with mock.patch.object(trial, 'TRIAL_ALLOWANCES', {}):
            self.assertFalse(trial.may(self.org, 'unbranded'))
            self.assertFalse(trial.use(self.org, 'unbranded', actor=self.editor))
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_lost_race_counts_against_the_winner(self):
        """
        GIVEN another request created the workspace's grant after this one decided it could start it
        WHEN this request's use() runs
        THEN it counts against the existing grant and creates no second one
        """
        from survey.models import Organization
        stale = Organization.objects.get(pk=self.org.pk)
        self.assertTrue(trial.startable(stale, 'api'))          # cached: "can start"
        trial.use(self.org, 'api', actor=self.editor)           # the other request wins
        self.assertTrue(trial.use(stale, 'api', actor=self.editor))
        self.assertEqual(EntitlementGrant.objects.count(), 1)
        self.assertEqual(GrantAllowance.objects.get(feature='api').used, 2)

    def test_refused_save_leaves_no_grant(self):
        """
        GIVEN a startable workspace and a use made inside a transaction that is rolled back afterwards
        WHEN the transaction fails
        THEN no grant remains
        """
        class Boom(Exception):
            pass
        with self.assertRaises(Boom):
            with transaction.atomic():
                trial.use(self.org, 'unbranded', actor=self.editor)
                raise Boom
        self.assertFalse(EntitlementGrant.objects.exists())

    def test_uncapped_allowance_is_counted_never_refused(self):
        """
        GIVEN a live trial whose operator_entry allowance has no limit and 10 000 uses
        WHEN another sheet is entered
        THEN use() is true and the count reads 10 001
        """
        grant = trial.claim(self.org, self.owner)
        _spend(grant, 'operator_entry', 10000)
        ents.forget(self.org)
        self.assertTrue(trial.use(self.org, 'operator_entry', actor=self.editor))
        self.assertEqual(grant.allowances.get(feature='operator_entry').used, 10001)

    def test_settings_switch_off_starts_the_trial(self):
        """
        GIVEN a startable workspace's survey with the badge on
        WHEN its settings are saved through the service with the badge off
        THEN the survey is unbranded and the trial exists with trigger "unbranded", unbranded 1 used
        """
        from survey.models import SurveyHeader
        from survey.services import surveys as svc
        from survey.services.context import Actor
        survey = SurveyHeader.objects.create(organization=self.org, name='auto_badge', redirect_url='#')
        svc.update_settings(Actor(user=self.owner), survey, {
            'name': 'auto_badge', 'redirect_url': '#', 'visibility': 'private', 'basemaps': '["streets"]',
            'default_basemap': 'streets'})
        survey.refresh_from_db()
        self.assertFalse(survey.show_branding)
        grant = EntitlementGrant.objects.get(organization=self.org)
        self.assertEqual((grant.trigger, grant.allowances.get(feature='unbranded').used), ('unbranded', 1))


class TrialMailTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.editor = _editor_of(self.org)

    def test_start_mail_names_the_editor(self):
        """
        GIVEN a startable workspace
        WHEN its editor starts the trial by entering a paper response and the transaction commits
        THEN the owner receives one mail naming the editor, the way it started, the allowances and the end date
        """
        from django.core import mail

        from .. import tasks
        # The suite has no broker: run the task where .delay would enqueue it.
        with mock.patch.object(tasks.send_trial_started, 'delay', side_effect=tasks.send_trial_started), \
                self.captureOnCommitCallbacks(execute=True):
            trial.use(self.org, 'operator_entry', actor=self.editor)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, [self.owner.email])
        self.assertIn('auto_editor', msg.body)
        self.assertIn('by entering a paper response', msg.body)
        self.assertIn('no limit', msg.body)

    def test_reminder_once(self):
        """
        GIVEN a live trial ending in 6 days
        WHEN notify_trials_ending runs twice
        THEN the owner gets one mail listing what stops, and ending_notified_at is set
        """
        from django.core import mail

        from ..tasks import notify_trials_ending
        grant = trial.claim(self.org, self.owner)
        EntitlementGrant.objects.filter(pk=grant.pk).update(expires_at=timezone.now() + timedelta(days=6))
        mail.outbox.clear()
        self.assertEqual(notify_trials_ending(), 1)
        self.assertEqual(notify_trials_ending(), 0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('entering paper responses closes', mail.outbox[0].body)
        self.assertIn('Nothing is deleted', mail.outbox[0].body)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.ending_notified_at)

    def test_no_reminder_for_pro_or_far_off_trials(self):
        """
        GIVEN one trial ending in 6 days on a workspace that bought Pro, and one ending in 30 days
        WHEN notify_trials_ending runs
        THEN no mail is sent
        """
        from django.core import mail

        from ..tasks import notify_trials_ending
        grant = trial.claim(self.org, self.owner)
        EntitlementGrant.objects.filter(pk=grant.pk).update(expires_at=timezone.now() + timedelta(days=6))
        make_sub(self.org)
        other, other_owner = make_org('Other Org', 'other_owner')
        trial.claim(other, other_owner)
        mail.outbox.clear()
        self.assertEqual(notify_trials_ending(), 0)
        self.assertEqual(mail.outbox, [])

    def test_no_mail_when_an_allowance_runs_out(self):
        """
        GIVEN a live trial with one pro_help request
        WHEN it is spent
        THEN no mail is sent
        """
        from django.core import mail
        trial.claim(self.org, self.owner)
        mail.outbox.clear()
        trial.use(self.org, 'pro_help', actor=self.editor)
        self.assertEqual(mail.outbox, [])
