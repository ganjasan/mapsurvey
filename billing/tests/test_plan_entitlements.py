"""Tests for the `plan-entitlements` capability.

Spec: openspec/changes/paywall-payproglobal/specs/plan-entitlements/spec.md
(after archive: openspec/specs/plan-entitlements/spec.md). One module per capability -- see #273.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.utils import timezone

from survey.editor_forms import SurveyHeaderForm
from survey.models import Membership, SurveyHeader

from .. import checkout as co
from .. import entitlements as ents
from .. import ipn as ipn_mod
from .. import ppg
from ..models import (
    STATUS_ACTIVE, STATUS_CHARGED_BACK, STATUS_FINISHED, STATUS_PAST_DUE, STATUS_REFUNDED,
    STATUS_SUSPENDED, STATUS_TERMINATED, BillingEvent, CheckoutIntent, ProHelpRequest, Subscription,
)
from ..tasks import notify_lapsed
from .helpers import PPG_IP, PPG_SETTINGS, make_org, make_sub as _sub, payload, post_ipn, sign


class EntitlementsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def test_no_subscription_is_free(self):
        """
        GIVEN an organisation without any subscription
        WHEN entitlements are computed
        THEN the plan is free with no features
        """
        e = ents.for_organization(self.org)
        self.assertEqual((e.plan, e.state, e.until), ('free', 'none', None))
        self.assertEqual(e.features, frozenset())

    def test_active_pro_has_both_features(self):
        """
        GIVEN an active subscription with a future period end
        WHEN entitlements are computed
        THEN the plan is pro, state active, with unbranded, pro_help and api
        """
        _sub(self.org)
        e = ents.for_organization(self.org)
        self.assertTrue(e.is_pro)
        self.assertEqual(e.state, 'active')
        self.assertEqual(e.features, frozenset({'unbranded', 'pro_help', 'api'}))

    def test_terminated_but_paid_is_cancelling(self):
        """
        GIVEN a terminated subscription whose period end is 10 days ahead
        WHEN entitlements are computed
        THEN the plan is still pro with state cancelling until that date
        """
        s = _sub(self.org, status=STATUS_TERMINATED, days=10)
        e = ents.for_organization(self.org)
        self.assertEqual((e.plan, e.state, e.until), ('pro', 'cancelling', s.current_period_end))

    def test_period_elapsed_is_lapsed(self):
        """
        GIVEN a suspended subscription whose period ended yesterday
        WHEN entitlements are computed
        THEN the plan is free with state lapsed
        """
        _sub(self.org, status=STATUS_SUSPENDED, days=-1)
        e = ents.for_organization(self.org)
        self.assertEqual((e.plan, e.state), ('free', 'lapsed'))

    def test_refunded_is_free_despite_future_date(self):
        """
        GIVEN a refunded subscription with a future period end still stored
        WHEN entitlements are computed
        THEN the plan is free
        """
        _sub(self.org, status=STATUS_REFUNDED, days=20)
        self.assertFalse(ents.for_organization(self.org).is_pro)

    def test_past_due_keeps_access(self):
        """
        GIVEN a past_due subscription within its period
        WHEN entitlements are computed
        THEN the plan is pro with state past_due
        """
        _sub(self.org, status=STATUS_PAST_DUE, days=5)
        e = ents.for_organization(self.org)
        self.assertEqual((e.plan, e.state), ('pro', 'past_due'))

    def test_finished_and_charged_back_are_free(self):
        for st in (STATUS_FINISHED, STATUS_CHARGED_BACK):
            Subscription.objects.all().delete()
            _sub(self.org, status=st, days=20)
            self.org._entitlements = None
            self.assertFalse(ents.for_organization(self.org).is_pro, st)

    def test_registry_drives_features(self):
        """
        GIVEN a new feature key added to the registry for plan pro
        WHEN entitlements are computed for a Pro organisation
        THEN the set contains it without any model change
        """
        from ..features import FEATURES, Feature
        _sub(self.org)
        with mock.patch.dict(FEATURES, {'custom_domain': Feature('custom_domain', frozenset({'pro'}), 'x')}):
            self.assertIn('custom_domain', ents.for_organization(self.org).features)

    def test_quota_seam_reads_entitlements(self):
        """
        GIVEN a Free organisation
        WHEN check_quota runs
        THEN it returns None and consulted the entitlement lookup
        """
        from survey.ai.quota import check_quota
        with mock.patch('billing.entitlements.for_organization', wraps=ents.for_organization) as spy:
            self.assertIsNone(check_quota(self.org, 'draft'))
            spy.assert_called_once()

    def test_template_tag_and_decorator(self):
        """
        GIVEN a Pro and a Free organisation
        WHEN has_feature is evaluated in a template
        THEN it is true only for the Pro one
        """
        free_org, _ = make_org('Free Org', 'free_owner')
        _sub(self.org)
        t = Template('{% load billing_tags %}{% has_feature org "unbranded" as u %}{{ u }}')
        self.assertEqual(t.render(Context({'org': self.org})), 'True')
        self.assertEqual(t.render(Context({'org': free_org})), 'False')


class NotifyLapsedTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def test_lapse_notified_once(self):
        """
        GIVEN a suspended subscription whose period ended yesterday
        WHEN notify_lapsed runs twice
        THEN one event and one owner email, and a second run sends nothing
        """
        _sub(self.org, status=STATUS_SUSPENDED, days=-1)
        _sub(self.org, status=STATUS_ACTIVE, days=10, ppg_subscription_id='222', superseded_at=None)
        with mock.patch('billing.events.emit') as emit:
            self.assertEqual(notify_lapsed(), 1)
            self.assertEqual(notify_lapsed(), 0)
        self.assertEqual([c.args[0] for c in emit.call_args_list], ['plan_lapsed'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('has ended', mail.outbox[0].subject)
