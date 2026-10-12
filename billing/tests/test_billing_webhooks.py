"""Tests for the `billing-webhooks` capability.

Spec: openspec/changes/paywall-payproglobal/specs/billing-webhooks/spec.md
(after archive: openspec/specs/billing-webhooks/spec.md). One module per capability -- see #273.
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
class IpnVerificationTest(TestCase):
    def test_documented_hash_examples(self):
        """
        GIVEN the examples in PayPro's documentation
        WHEN the hash helpers run
        THEN they reproduce the documented digests
        """
        self.assertEqual(ipn_mod.expected_hash('1', 'ignored', True), 'c4ca4238a0b923820dcc509a6f75849b')
        self.assertEqual(ipn_mod.expected_hash('456346', 'wErt6HmQ', False), 'cdcca12c15a93df32818e463af053fbc')
        sample = {'ORDER_ID': '12345', 'ORDER_STATUS': 'Processed', 'ORDER_TOTAL_AMOUNT': '9.99',
                  'CUSTOMER_EMAIL': 'test@payproglobal.com', 'TEST_MODE': '1', 'IPN_TYPE_NAME': 'OrderCharged'}
        import hashlib
        self.assertEqual(ipn_mod.expected_signature(sample, 'qwerty'),
                         hashlib.sha256(b'12345Processed9.99test@payproglobal.comqwerty1OrderCharged').hexdigest())

    def test_valid_event_passes(self):
        p = payload(1, 'OrderCharged')
        self.assertEqual(ipn_mod.verify(p, PPG_IP), ['ip', 'signature', 'hash'])

    def test_wrong_signature_rejected(self):
        p = payload(1, 'OrderCharged')
        p['SIGNATURE'] = 'f' * 64
        with self.assertRaises(ipn_mod.IpnVerificationError):
            ipn_mod.verify(p, PPG_IP)

    def test_wrong_hash_rejected(self):
        p = payload(1, 'OrderCharged')
        p['HASH'] = 'f' * 32
        with self.assertRaises(ipn_mod.IpnVerificationError):
            ipn_mod.verify(p, PPG_IP)

    def test_unknown_ip_rejected(self):
        with self.assertRaises(ipn_mod.IpnVerificationError):
            ipn_mod.verify(payload(1, 'OrderCharged'), '1.1.1.1')

    def test_test_order_hash(self):
        p = payload(1, 'OrderCharged', test_mode=True)
        self.assertEqual(p['HASH'], 'c4ca4238a0b923820dcc509a6f75849b')
        ipn_mod.verify(p, PPG_IP)

    def test_body_hash_ignores_resent_marker(self):
        p = payload(1, 'OrderCharged')
        self.assertEqual(ipn_mod.body_sha256(p), ipn_mod.body_sha256({**p, 'IS_RESENT': '1'}))

    def test_custom_fields_and_dates(self):
        self.assertEqual(ipn_mod.parse_custom_fields('x-org_id=42,x-nonce=abc'), {'x-org_id': '42', 'x-nonce': 'abc'})
        self.assertEqual(ipn_mod.parse_custom_fields('x-testuser=123'), {'x-testuser': '123'})
        self.assertIsNotNone(ipn_mod.parse_ppg_datetime('2024-03-29T11:29:59.837'))
        self.assertIsNotNone(ipn_mod.parse_ppg_datetime('3/29/2024'))
        self.assertIsNone(ipn_mod.parse_ppg_datetime('nonsense'))
        self.assertTrue(timezone.is_aware(ipn_mod.parse_ppg_datetime('2024-03-29T11:29:59')))


@override_settings(**PPG_SETTINGS)
class IpnEndpointTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def _charge(self, **kw):
        return post_ipn(self.client, payload(1, 'OrderCharged', org_id=self.org.pk, **kw))

    def test_initial_purchase_creates_subscription(self):
        """
        GIVEN an OrderCharged with x-org_id, a known product and a next charge date
        WHEN it is posted from a PayPro IP with valid signatures
        THEN the organisation gets an active pro subscription with that period end
        """
        r = self._charge()
        self.assertEqual(r.status_code, 200)
        sub = Subscription.objects.get(organization=self.org)
        self.assertEqual((sub.plan_code, sub.status, sub.ppg_subscription_id, sub.product_key),
                         ('pro', STATUS_ACTIVE, '954874', 'pro_yearly'))
        self.assertAlmostEqual(sub.current_period_end, timezone.now() + timedelta(days=365), delta=timedelta(minutes=1))
        self.assertEqual(sub.renewal_type, 'auto')
        self.assertEqual(sub.last_invoice_url, 'https://invoice.example.test/1')
        self.assertTrue(ents.for_organization(self.org).is_pro)
        ev = BillingEvent.objects.get()
        self.assertEqual((ev.organization, ev.subscription, ev.error), (self.org, sub, ''))

    def test_wrong_signature_is_400_and_nothing_stored(self):
        p = payload(1, 'OrderCharged', org_id=self.org.pk)
        p['SIGNATURE'] = 'f' * 64
        self.assertEqual(post_ipn(self.client, p).status_code, 400)
        self.assertFalse(BillingEvent.objects.exists())

    def test_unknown_ip_is_400(self):
        self.assertEqual(post_ipn(self.client, payload(1, 'OrderCharged', org_id=self.org.pk), ip='8.8.8.8').status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get('/billing/ipn/').status_code, 405)

    def test_resend_is_acknowledged_once_applied(self):
        """
        GIVEN a SubscriptionChargeSucceed applied once
        WHEN the same body arrives again with IS_RESENT=1
        THEN one event exists, the period end was extended once, both responses were 200
        """
        self._charge()
        end = timezone.now() + timedelta(days=400)
        p = payload(6, 'SubscriptionChargeSucceed', order_id='5002', next_charge=end)
        self.assertEqual(post_ipn(self.client, p).status_code, 200)
        self.assertEqual(post_ipn(self.client, {**p, 'IS_RESENT': '1'}).status_code, 200)
        self.assertEqual(BillingEvent.objects.filter(ipn_type_id=6).count(), 1)
        sub = Subscription.objects.get(organization=self.org)
        self.assertAlmostEqual(sub.current_period_end, end, delta=timedelta(seconds=1))

    def test_test_mode_ignored_on_production(self):
        """
        GIVEN PPG_ACCEPT_TEST_IPN=false
        WHEN a TEST_MODE=1 OrderCharged arrives
        THEN it is stored as ignored_test, no subscription is created, response 200
        """
        r = self._charge(test_mode=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(BillingEvent.objects.get().ignored_test)
        self.assertFalse(Subscription.objects.exists())

    @override_settings(PPG_ACCEPT_TEST_IPN=True)
    def test_test_mode_applied_on_preview(self):
        self._charge(test_mode=True)
        self.assertTrue(Subscription.objects.filter(organization=self.org).exists())

    def test_resolution_by_subscription_id_then_email(self):
        """
        GIVEN a stored subscription and a rebill with no custom fields
        WHEN it arrives
        THEN it is matched by SUBSCRIPTION_ID; an unknown subscription falls back to the owner email
        """
        self._charge()
        p = payload(6, 'SubscriptionChargeSucceed', order_id='5003', extra={'ORDER_CUSTOM_FIELDS': ''})
        post_ipn(self.client, p)
        self.assertEqual(BillingEvent.objects.get(ipn_type_id=6).organization, self.org)
        # unknown subscription, no custom fields, but the owner's email
        Subscription.objects.all().delete()
        p = payload(1, 'OrderCharged', order_id='5004', subscription_id='999', extra={'ORDER_CUSTOM_FIELDS': ''})
        post_ipn(self.client, p)
        self.assertEqual(Subscription.objects.get(organization=self.org).ppg_subscription_id, '999')

    def test_unresolvable_event_stored_with_error(self):
        p = payload(1, 'OrderCharged', email='nobody@example.test', extra={'ORDER_CUSTOM_FIELDS': ''})
        self.assertEqual(post_ipn(self.client, p).status_code, 200)
        self.assertEqual(BillingEvent.objects.get().error, 'unresolved')
        self.assertFalse(Subscription.objects.exists())

    def test_unknown_product_not_granted(self):
        self._charge(product_id=5555)
        self.assertEqual(BillingEvent.objects.get().error, 'unknown_product')
        self.assertFalse(Subscription.objects.exists())

    def test_nonce_resolves_and_consumes_intent(self):
        """
        GIVEN a checkout intent
        WHEN OrderCharged arrives carrying its nonce and no x-org_id
        THEN the intent's organisation is used and the intent is marked consumed with the order id
        """
        intent = CheckoutIntent.objects.create(organization=self.org, user=self.owner, product_key='pro_yearly')
        p = payload(1, 'OrderCharged', nonce=str(intent.nonce), email='other@example.test')
        post_ipn(self.client, p)
        intent.refresh_from_db()
        self.assertEqual((intent.order_id, intent.consumed_at is not None), ('5001', True))
        self.assertTrue(Subscription.objects.filter(organization=self.org).exists())

    def test_dunning_then_suspension(self):
        """
        GIVEN an active subscription
        WHEN SubscriptionChargeFailed arrives three times and then SubscriptionSuspended
        THEN status goes past_due then suspended, attempts are counted, period end unchanged
        """
        self._charge()
        sub = Subscription.objects.get()
        end = sub.current_period_end
        for n in (1, 2, 3):
            post_ipn(self.client, payload(7, 'SubscriptionChargeFailed', order_id='6001',
                                          extra={'SUBSCRIPTION_NUMBER_OF_FAILED_ATTEMPTS': str(n)}))
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.failed_attempts), (STATUS_PAST_DUE, 3))
        post_ipn(self.client, payload(8, 'SubscriptionSuspended', order_id='6001',
                                      extra={'SUBSCRIPTION_STATUS_ID': '2', 'SUBSCRIPTION_CANCELLATION_REASON_ID': '2',
                                             'ACTION_REASON': 'card declined'}))
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.cancellation_reason_id, sub.action_reason), (STATUS_SUSPENDED, 2, 'card declined'))
        self.assertEqual(sub.current_period_end, end)
        self.assertTrue(ents.for_organization(self.org).is_pro)  # paid up until `end`

    def test_renewed_then_charge_restores(self):
        self._charge()
        post_ipn(self.client, payload(8, 'SubscriptionSuspended', order_id='6001'))
        post_ipn(self.client, payload(9, 'SubscriptionRenewed', order_id='6002'))
        self.assertEqual(Subscription.objects.get().status, STATUS_ACTIVE)

    def test_terminated_finished_refunded_chargeback(self):
        self._charge()
        sub = Subscription.objects.get()
        post_ipn(self.client, payload(10, 'SubscriptionTerminated', order_id='7001'))
        sub.refresh_from_db()
        self.assertEqual(sub.status, STATUS_TERMINATED)
        self.assertTrue(ents.for_organization(self.org).is_pro)
        post_ipn(self.client, payload(11, 'SubscriptionFinished', order_id='7002'))
        sub.refresh_from_db()
        self.assertEqual(sub.status, STATUS_FINISHED)
        self.assertLessEqual(sub.current_period_end, timezone.now())
        self.org._entitlements = None
        self.assertFalse(ents.for_organization(self.org).is_pro)

    def test_refund_cuts_now(self):
        self._charge()
        post_ipn(self.client, payload(2, 'OrderRefunded', status='Refunded', extra={'REFUND_ISSUED_BY': 'Vendor'}))
        sub = Subscription.objects.get()
        self.assertEqual(sub.status, STATUS_REFUNDED)
        self.assertLessEqual(sub.current_period_end, timezone.now())
        self.assertFalse(ents.for_organization(self.org).is_pro)

    def test_chargeback_cuts_and_flags(self):
        self._charge()
        post_ipn(self.client, payload(3, 'OrderChargedBack', status='Chargeback'))
        sub = Subscription.objects.get()
        self.assertEqual((sub.status, sub.needs_review), (STATUS_CHARGED_BACK, True))
        post_ipn(self.client, payload(14, 'OrderChargedBackWon', status='Processed'))
        sub.refresh_from_db()
        self.assertEqual(sub.status, STATUS_CHARGED_BACK)  # no automatic restore

    def test_replacement_purchase_supersedes(self):
        """
        GIVEN an organisation with a current monthly subscription
        WHEN OrderCharged arrives with a new SUBSCRIPTION_ID
        THEN the old row is superseded and the new one is current
        """
        self._charge(subscription_id='111', product_id=1001)
        self._charge(subscription_id='222', product_id=1002, order_id='5009')
        old = Subscription.objects.get(ppg_subscription_id='111')
        new = Subscription.objects.get(ppg_subscription_id='222')
        self.assertIsNotNone(old.superseded_at)
        self.assertIsNone(new.superseded_at)
        self.assertEqual(ents.current_subscription(self.org), new)

    def test_customer_info_change_and_passthrough(self):
        self._charge()
        post_ipn(self.client, payload(15, 'OrderCustomerInformationChanged', email='new@example.test'))
        self.assertEqual(Subscription.objects.get().customer_email, 'new@example.test')
        post_ipn(self.client, payload(17, 'OrderOnWaiting', status='Waiting', order_id='8001'))
        self.assertEqual(BillingEvent.objects.get(ipn_type_id=17).error, '')
        self.assertEqual(Subscription.objects.get().status, STATUS_ACTIVE)

    def test_apply_failure_rolls_back_and_500s(self):
        """
        GIVEN applying an event raises
        WHEN the webhook is posted
        THEN no BillingEvent remains and the status is 500
        """
        with mock.patch('billing.ipn.apply', side_effect=RuntimeError('boom')):
            self.client.raise_request_exception = False
            r = self._charge()
        self.assertEqual(r.status_code, 500)
        self.assertFalse(BillingEvent.objects.exists())

    def test_activation_emitted_once(self):
        with mock.patch('billing.events.emit') as emit:
            self._charge()
            self._charge()  # duplicate
        names = [c.args[0] for c in emit.call_args_list]
        self.assertEqual(names.count('plan_activated'), 1)

    def test_payment_failed_emitted_once_per_cycle(self):
        self._charge()
        with mock.patch('billing.events.emit') as emit:
            for n in (1, 2):
                post_ipn(self.client, payload(7, 'SubscriptionChargeFailed', order_id='6001',
                                              extra={'SUBSCRIPTION_NUMBER_OF_FAILED_ATTEMPTS': str(n)}))
        self.assertEqual([c.args[0] for c in emit.call_args_list].count('plan_payment_failed'), 1)


# ---------------------------------------------------------------------------
# Real payload (task 3.5)
# ---------------------------------------------------------------------------

def _real_order_charged(org_id):
    import json
    import os
    path = os.path.join(os.path.dirname(__file__), 'fixtures', 'order_charged_test_mode.json')
    p = dict(json.load(open(path))['payload'])
    p['ORDER_CUSTOM_FIELDS'] = p['ORDER_CUSTOM_FIELDS'].replace('x-org_id=1', f'x-org_id={org_id}')
    return sign(p)


@override_settings(**{**PPG_SETTINGS, 'PPG_PRODUCTS': {'pro_monthly': 138966, 'pro_yearly': 138969},
                      'PPG_ACCEPT_TEST_IPN': True})
class RealPayloadTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()

    def test_real_order_charged_sets_period_end(self):
        """
        GIVEN the OrderCharged PayPro actually sent on the preview (test mode, 2026-10-12)
        WHEN it is posted to the webhook
        THEN the subscription ends its period at 2026-11-12 11:36 UTC, as written in
             SUBSCRIPTION_NEXT_CHARGE_DATE ("11/12/2026 11:36 AM", month first, 12-hour clock)
        """
        from datetime import datetime, timezone as dt_tz
        r = post_ipn(self.client, _real_order_charged(self.org.pk))
        self.assertEqual(r.status_code, 200)
        sub = Subscription.objects.get(organization=self.org)
        self.assertEqual(sub.current_period_end, datetime(2026, 11, 12, 11, 36, tzinfo=dt_tz.utc))
        self.assertEqual(sub.current_period_end_raw, '11/12/2026 11:36 AM')
        self.assertEqual((sub.product_key, sub.ppg_subscription_id, sub.renewal_type), ('pro_monthly', '5411153', 'auto'))
        at_purchase = datetime(2026, 10, 12, 12, 0, tzinfo=dt_tz.utc)
        self.assertTrue(ents.for_subscription(sub, at_purchase).is_pro)

    def test_real_custom_fields_and_order_time(self):
        p = _real_order_charged(self.org.pk)
        self.assertEqual(ipn_mod.parse_custom_fields(p['ORDER_CUSTOM_FIELDS'])['x-plan'], 'pro_monthly')
        self.assertEqual(ipn_mod.parse_ppg_datetime(p['ORDER_PLACED_TIME_UTC']).month, 10)

    def test_unparseable_date_still_grants_one_period(self):
        """
        GIVEN a paid OrderCharged whose next charge date is in a format we cannot read
        WHEN it is applied
        THEN the raw string is stored and the subscription gets one product period, not "Ended"
        """
        p = _real_order_charged(self.org.pk)
        p['SUBSCRIPTION_NEXT_CHARGE_DATE'] = 'next Thursday'
        post_ipn(self.client, sign(p))
        sub = Subscription.objects.get(organization=self.org)
        self.assertEqual(sub.current_period_end_raw, 'next Thursday')
        self.assertAlmostEqual(sub.current_period_end, timezone.now() + timedelta(days=31), delta=timedelta(days=3))
        self.assertTrue(ents.for_organization(self.org).is_pro)
