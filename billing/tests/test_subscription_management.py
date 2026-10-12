"""Tests for the `subscription-management` capability.

Spec: openspec/changes/paywall-payproglobal/specs/subscription-management/spec.md
(after archive: openspec/specs/subscription-management/spec.md). One module per capability -- see #273.
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


@override_settings(**PPG_SETTINGS)
class BillingPageTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.admin = User.objects.create_user(username='bill_admin', password='pass')
        self.editor = User.objects.create_user(username='bill_editor', password='pass')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        self.url = f'/org/{self.org.slug}/billing/'

    def test_visibility_by_role(self):
        self.client.login(username='bill_admin', password='pass')
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.login(username='bill_editor', password='pass')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_active_page_shows_state_and_links(self):
        _sub(self.org)
        self.client.login(username='bill_owner', password='pass')
        html = self.client.get(self.url).content.decode()
        self.assertIn('Renews automatically', html)
        self.assertIn('subscr-id=954874', html)
        self.assertIn('cc.payproglobal.com/Customer/Account/Login', html)
        self.assertIn('Cancelling and refunds', html)
        self.assertNotIn('Cancel plan', html)  # no API key

    def test_past_due_and_manual_copy(self):
        _sub(self.org, status=STATUS_PAST_DUE, failed_attempts=2)
        self.client.login(username='bill_owner', password='pass')
        self.assertContains(self.client.get(self.url), 'Payment failed')
        Subscription.objects.update(status=STATUS_ACTIVE, renewal_type='manual')
        self.assertContains(self.client.get(self.url), 'Renews by invoice')

    def test_cancelling_copy(self):
        _sub(self.org, status=STATUS_TERMINATED, days=10)
        self.client.login(username='bill_owner', password='pass')
        self.assertContains(self.client.get(self.url), 'then the organisation returns to Free')

    def test_awaiting_transfer_and_duplicates(self):
        sub = _sub(self.org)
        BillingEvent.objects.create(ipn_type_id=17, ipn_type_name='OrderOnWaiting', order_id='8001', body_sha256='x',
                                    payload={}, organization=self.org)
        _sub(self.org, ppg_subscription_id='111', superseded_at=timezone.now())
        self.client.login(username='bill_owner', password='pass')
        html = self.client.get(self.url).content.decode()
        self.assertIn('awaiting your bank transfer', html)
        self.assertIn('#111', html)

    def test_actions_404_without_api_key(self):
        _sub(self.org)
        self.client.login(username='bill_owner', password='pass')
        for path in ('cancel', 'resubscribe', 'switch', 'login-link'):
            self.assertEqual(self.client.post(f'{self.url}{path}/', {'reason': '2'}).status_code, 404, path)

    @override_settings(PPG_API_SECRET_KEY='k', PPG_VENDOR_ACCOUNT_ID='1')
    def test_cancel_with_api(self):
        """
        GIVEN the API is configured
        WHEN the owner confirms cancellation with a reason
        THEN Suspend is called with the reason id, a pending marker is set, status unchanged
        """
        sub = _sub(self.org)
        self.client.login(username='bill_owner', password='pass')
        self.assertContains(self.client.get(self.url), 'Cancel plan')
        with mock.patch('billing.ppg._post', return_value={'isSuccess': True, 'errors': []}) as post:
            r = self.client.post(f'{self.url}cancel/', {'reason': '2', 'note': 'moving on'}, follow=True)
        post.assert_called_once()
        self.assertEqual(post.call_args.args[0], 'Subscriptions/Suspend')
        self.assertEqual(post.call_args.args[1]['cancellationReasonId'], 2)
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.pending_change), (STATUS_ACTIVE, 'cancel'))
        self.assertContains(r, 'Cancellation requested')
        # the webhook clears the marker
        post_ipn(self.client, payload(8, 'SubscriptionSuspended', org_id=self.org.pk))
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.pending_change), (STATUS_SUSPENDED, ''))

    @override_settings(PPG_API_SECRET_KEY='k', PPG_VENDOR_ACCOUNT_ID='1')
    def test_api_error_surfaced(self):
        _sub(self.org)
        self.client.login(username='bill_owner', password='pass')
        err = ppg.PPGApiError('Subscriptions/Suspend', [{'propertyWithError': 'subscriptionId', 'propertyErrorMessages': ['not found']}])
        with mock.patch('billing.ppg._post', side_effect=err):
            r = self.client.post(f'{self.url}cancel/', {'reason': '2'}, follow=True)
        self.assertContains(r, 'subscriptionId: not found')
        self.assertEqual(Subscription.objects.get().pending_change, '')

    @override_settings(PPG_API_SECRET_KEY='k', PPG_VENDOR_ACCOUNT_ID='1')
    def test_resubscribe_switch_and_login_link(self):
        sub = _sub(self.org, status=STATUS_SUSPENDED)
        self.client.login(username='bill_owner', password='pass')
        with mock.patch('billing.ppg._post', return_value={'isSuccess': True}) as post:
            self.client.post(f'{self.url}resubscribe/')
            self.client.post(f'{self.url}login-link/')
            Subscription.objects.update(status=STATUS_ACTIVE)
            self.client.post(f'{self.url}switch/')
        endpoints = [c.args[0] for c in post.call_args_list]
        self.assertEqual(endpoints, ['Subscriptions/Renew', 'Customers/SendOnetimeLoginEmail', 'Subscriptions/ChangeProduct'])
        self.assertEqual(post.call_args_list[2].args[1]['productId'], 1002)
