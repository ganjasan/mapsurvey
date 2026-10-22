"""`api-pro-gate`: feature `api`, checked at the resource on the owning organisation."""
from datetime import timedelta

from django.test import RequestFactory, TestCase
from django.utils import timezone

from billing.features import PLAN_FREE, PLAN_PRO, features_for_plan
from billing.models import STATUS_REFUNDED
from survey.models import Membership, SurveyCollaborator

from .. import auth, gates
from ..errors import ApiError
from ..models import AUDIENCE_API
from .helpers import LOCMEM, bearer, make_free_org, make_member, make_pro_org, make_sub, make_survey, mint


def principal_for(user, **kw):
    value, _ = mint(user, **kw)
    return auth.authenticate(RequestFactory().get('/', **bearer(value)), AUDIENCE_API)


class RegistryTest(TestCase):
    def test_api_is_pro_only(self):
        """
        GIVEN the feature registry
        WHEN plans are read
        THEN api is in Pro and not in Free
        """
        self.assertIn('api', features_for_plan(PLAN_PRO))
        self.assertNotIn('api', features_for_plan(PLAN_FREE))


@LOCMEM
class GateTest(TestCase):
    def setUp(self):
        self.pro, self.pro_owner = make_pro_org()
        self.free, self.free_owner = make_free_org()
        self.pro_survey, _, _ = make_survey(self.pro, 'pro_survey')
        self.free_survey, _, _ = make_survey(self.free, 'free_survey')

    def _refused(self, principal, org):
        with self.assertRaises(ApiError) as cm:
            gates.require_pro_api(principal, org)
        self.assertEqual(cm.exception.status, 403)
        self.assertEqual(cm.exception.code, 'pro_required')
        return cm.exception

    def test_free_workspace_survey_refused_even_for_a_pro_user(self):
        """
        GIVEN the Pro workspace's owner is also owner of a Free workspace
        WHEN the gate runs on the Free survey's organisation
        THEN 403 pro_required naming the Free workspace with its upgrade link
        """
        Membership.objects.create(user=self.pro_owner, organization=self.free, role='owner')
        err = self._refused(principal_for(self.pro_owner), self.free_survey.organization)
        self.assertEqual(err.extra['organization'], self.free.slug)
        self.assertIn(f'/{self.free.slug}/billing/', err.extra['upgrade_url'])
        self.assertTrue(err.extra['upgrade_url'].startswith('http'))

    def test_free_collaborator_on_pro_survey_allowed(self):
        """
        GIVEN a user whose own workspace is Free, collaborating on a Pro workspace's survey
        WHEN the gate runs on the Pro survey's organisation
        THEN allowed
        """
        Membership.objects.create(user=self.free_owner, organization=self.pro, role='editor')
        SurveyCollaborator.objects.create(user=self.free_owner, survey=self.pro_survey, role='editor')
        gates.require_pro_api(principal_for(self.free_owner), self.pro_survey.organization)

    def test_lapse_between_two_calls(self):
        """
        GIVEN a Pro subscription
        WHEN its period ends between two calls with the same token
        THEN the first passes, the second is pro_required, the token row is unchanged
        """
        p = principal_for(self.pro_owner)
        gates.require_pro_api(p, self.pro)
        sub = self.pro.subscriptions.first() if hasattr(self.pro, 'subscriptions') else None
        from billing.models import Subscription
        sub = Subscription.objects.filter(organization=self.pro).first()
        sub.current_period_end = timezone.now() - timedelta(seconds=1)
        sub.save(update_fields=['current_period_end'])
        self.pro._entitlements = None
        self._refused(p, self.pro)
        p.profile.refresh_from_db()
        self.assertIsNone(p.profile.revoked_at)

    def test_renewal_restores_the_same_token(self):
        """
        GIVEN a lapsed subscription
        WHEN the period end is extended again
        THEN the same token passes without re-minting
        """
        from billing.models import Subscription
        p = principal_for(self.pro_owner)
        sub = Subscription.objects.filter(organization=self.pro).first()
        sub.current_period_end = timezone.now() - timedelta(days=1)
        sub.save(update_fields=['current_period_end'])
        self.pro._entitlements = None
        self._refused(p, self.pro)
        sub.current_period_end = timezone.now() + timedelta(days=30)
        sub.save(update_fields=['current_period_end'])
        self.pro._entitlements = None
        gates.require_pro_api(p, self.pro)

    def test_refund_refuses(self):
        """
        GIVEN a subscription moved to refunded
        WHEN the gate runs
        THEN pro_required
        """
        from billing.models import Subscription
        Subscription.objects.filter(organization=self.pro).update(status=STATUS_REFUNDED)
        self.pro._entitlements = None
        self._refused(principal_for(self.pro_owner), self.pro)

    def test_none_organization_refused(self):
        """
        GIVEN no organisation
        WHEN the gate runs
        THEN pro_required with no upgrade link
        """
        err = self._refused(principal_for(self.pro_owner), None)
        self.assertIsNone(err.extra['upgrade_url'])


@LOCMEM
class ProOrganizationsTest(TestCase):
    def test_counts_hidden_by_plan(self):
        """
        GIVEN a member of one Pro and two Free workspaces
        WHEN pro_organizations runs
        THEN the Pro one is returned and hidden_by_plan is 2
        """
        pro, owner = make_pro_org()
        free1, _ = make_free_org('Free 1', 'f1')
        free2, _ = make_free_org('Free 2', 'f2')
        Membership.objects.create(user=owner, organization=free1, role='viewer')
        Membership.objects.create(user=owner, organization=free2, role='editor')
        allowed, hidden = gates.pro_organizations(principal_for(owner))
        self.assertEqual(allowed, [pro])
        self.assertEqual(hidden, 2)

    def test_bound_token_sees_only_its_workspace(self):
        """
        GIVEN a token bound to a Free workspace of a user who also has a Pro one
        WHEN pro_organizations runs
        THEN nothing is allowed and one is hidden
        """
        pro, owner = make_pro_org()
        free, _ = make_free_org()
        Membership.objects.create(user=owner, organization=free, role='owner')
        allowed, hidden = gates.pro_organizations(principal_for(owner, organization=free))
        self.assertEqual((allowed, hidden), ([], 1))
