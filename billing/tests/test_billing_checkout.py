"""Tests for the `billing-checkout` capability.

Spec: openspec/changes/paywall-payproglobal/specs/billing-checkout/spec.md
(after archive: openspec/specs/billing-checkout/spec.md). One module per capability -- see #273.
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
class CheckoutTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.admin = User.objects.create_user(username='bill_admin', password='pass', email='a@example.test')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')

    @override_settings(ALLOWED_HOSTS=['mapsurvey-pr-12.onrender.com', 'testserver'])
    def test_owner_starts_checkout_with_identifiers(self):
        """
        GIVEN an owner on a preview host
        WHEN they submit the checkout form for yearly
        THEN an intent exists and the redirect carries product, x-* fields, email and ipn-domain
        """
        self.client.login(username='bill_owner', password='pass')
        r = self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'yearly'},
                             HTTP_HOST='mapsurvey-pr-12.onrender.com')
        self.assertEqual(r.status_code, 302)
        intent = CheckoutIntent.objects.get()
        url = r['Location']
        self.assertTrue(url.startswith('https://store.payproglobal.com/checkout?'))
        for part in ('products[1][id]=1002', f'x-org_id={self.org.pk}', f'x-user_id={self.owner.pk}',
                     'x-plan=pro_yearly', f'x-nonce={intent.nonce}', 'billing-email=bill_owner%40example.test',
                     'ipn-domain=mapsurvey-pr-12.onrender.com', 'use-company-purchase=true'):
            self.assertIn(part, url, part)
        self.assertNotIn('use-test-mode', url)
        self.assertNotIn('display-quote', url)

    def test_monthly_has_no_company_or_quote(self):
        self.client.login(username='bill_owner', password='pass')
        url = self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'monthly'})['Location']
        self.assertIn('products[1][id]=1001', url)
        self.assertNotIn('use-company-purchase', url)
        self.assertNotIn('display-quote', url)

    def test_quote_variant(self):
        self.client.login(username='bill_owner', password='pass')
        url = self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'yearly', 'quote': '1'})['Location']
        self.assertIn('display-quote=true', url)
        self.assertIn('quote-mode=editable', url)
        self.assertTrue(CheckoutIntent.objects.get().quote)

    @override_settings(PPG_TEST_MODE=True)
    def test_test_mode_adds_parameters(self):
        self.client.login(username='bill_owner', password='pass')
        url = self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'monthly'})['Location']
        self.assertIn('use-test-mode=true', url)
        self.assertIn('secret-key=secret-key-test', url)

    def test_admin_cannot_start_checkout(self):
        self.client.login(username='bill_admin', password='pass')
        r = self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'monthly'})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(CheckoutIntent.objects.exists())

    @override_settings(PPG_PRODUCTS={})
    def test_unconfigured_products_hide_controls(self):
        self.client.login(username='bill_owner', password='pass')
        self.assertEqual(self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'monthly'}).status_code, 404)
        html = self.client.get(f'/org/{self.org.slug}/settings/').content.decode()
        self.assertNotIn('Upgrade — monthly', html)
        html = self.client.get(f'/org/{self.org.slug}/billing/').content.decode()
        self.assertNotIn('Upgrade — monthly', html)

    def test_custom_value_separator_guard(self):
        with self.assertRaises(ValueError):
            co.build_checkout_url(product_key='pro_monthly', organization=self.org, user=self.owner, nonce='a,b')

    def test_return_page_states(self):
        """
        GIVEN an intent
        WHEN the return page and status endpoint are hit before and after activation
        THEN they report pending then active, and the page never writes a subscription
        """
        intent = CheckoutIntent.objects.create(organization=self.org, user=self.owner, product_key='pro_yearly')
        self.client.login(username='bill_owner', password='pass')
        r = self.client.get(f'/billing/return/?x-nonce={intent.nonce}')
        self.assertContains(r, 'Activating your Pro plan')
        self.assertEqual(self.client.get(f'/billing/return/status/?nonce={intent.nonce}').json(), {'state': 'pending'})
        self.assertFalse(Subscription.objects.exists())
        _sub(self.org)
        self.assertEqual(self.client.get(f'/billing/return/status/?nonce={intent.nonce}').json(), {'state': 'active'})
        # PayPro's POST form of the redirect
        r = self.client.post(f'/billing/return/', {'ORDER_CUSTOM_FIELDS': f'x-org_id=1,x-nonce={intent.nonce}'})
        self.assertEqual(r.status_code, 200)

    def test_return_page_waiting_and_unknown(self):
        r = self.client.get('/billing/return/?pending=1')
        self.assertContains(r, 'bank transfer')
        r = self.client.get('/billing/return/?x-nonce=00000000-0000-0000-0000-000000000000')
        self.assertContains(r, 'processing your order')
        self.assertEqual(self.client.get('/billing/return/status/?nonce=nope').json(), {'state': 'unknown'})

    def test_checkout_event_emitted(self):
        self.client.login(username='bill_owner', password='pass')
        with mock.patch('billing.events.emit') as emit:
            self.client.post(f'/org/{self.org.slug}/billing/checkout/', {'period': 'monthly'})
        self.assertEqual(emit.call_args.args[0], 'plan_checkout_started')


@override_settings(**PPG_SETTINGS)
class ReturnForwardTest(TestCase):
    """PayPro has one thank-you URL (production); previews get their buyers back by forwarding."""

    def test_forwards_to_originating_preview(self):
        """
        GIVEN PayPro's thank-you redirect to production carrying ipn-domain of a PR preview
        WHEN the return page is hit (POST with the order, original query via GET)
        THEN the buyer is sent with a 303 to that preview's return page, nonce kept
        """
        r = self.client.post('/billing/return/?x-nonce=abc&ipn-domain=mapsurvey-pr-276.onrender.com',
                             {'ORDER_ID': '1'})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r['Location'], 'https://mapsurvey-pr-276.onrender.com/billing/return/?x-nonce=abc')

    def test_forward_from_posted_query_string_and_pending(self):
        r = self.client.post('/billing/return/?pending=1',
                             {'CHECKOUT_QUERY_STRING': 'products[1][id]=1&x-nonce=n1&ipn-domain=mapsurvey-pr-9.onrender.com',
                              'ORDER_CUSTOM_FIELDS': 'x-nonce=n1'})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r['Location'], 'https://mapsurvey-pr-9.onrender.com/billing/return/?x-nonce=n1&pending=1')

    def test_never_an_open_redirect(self):
        """
        GIVEN an ipn-domain that is not a PR preview host
        WHEN the return page is hit
        THEN it renders here and does not redirect
        """
        for host in ('evil.example', 'mapsurvey-pr-1.onrender.com.evil.example', 'xmapsurvey-pr-1.onrender.com'):
            r = self.client.get(f'/billing/return/?x-nonce=abc&ipn-domain={host}')
            self.assertEqual(r.status_code, 200, host)

    @override_settings(ALLOWED_HOSTS=['mapsurvey-pr-276.onrender.com', 'testserver'])
    def test_no_forward_to_itself(self):
        r = self.client.get('/billing/return/?ipn-domain=mapsurvey-pr-276.onrender.com',
                            HTTP_HOST='mapsurvey-pr-276.onrender.com')
        self.assertEqual(r.status_code, 200)
