"""Tests for the `pro-help-channel` capability.

Spec: openspec/changes/paywall-payproglobal/specs/pro-help-channel/spec.md
(after archive: openspec/specs/pro-help-channel/spec.md). One module per capability -- see #273.
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
from .helpers import PPG_IP, PPG_SETTINGS, make_org, make_sub as _sub, payload, post_ipn, sign, trial_used_elsewhere


@override_settings(**PPG_SETTINGS)
class ProHelpTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.editor = User.objects.create_user(username='bill_editor', password='pass', email='ed@example.test')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        self.url = f'/org/{self.org.slug}/help/'

    def test_free_sees_offer_and_cannot_post(self):
        """
        GIVEN the owner of a Free organisation who already used their Pro trial in another workspace
        WHEN they open the help page and then POST to it
        THEN the page describes the service with no form, and the POST is 403
        """
        trial_used_elsewhere(self.org)
        self.client.login(username='bill_owner', password='pass')
        r = self.client.get(self.url)
        self.assertNotContains(r, 'Send request')
        self.assertNotContains(r, f'/org/{self.org.slug}/billing/trial/')
        self.assertEqual(self.client.post(self.url, {'kind': 'report', 'message': 'x', 'contact_email': 'a@b.c'}).status_code, 403)
        self.assertFalse(ProHelpRequest.objects.exists())

    def test_startable_member_sees_the_form_and_the_first_request_starts_the_trial(self):
        """
        GIVEN a Free organisation that never had a trial, and an editor of it
        WHEN the editor opens the help page and then sends a valid request
        THEN the form renders with "starts your workspace's free Pro trial" and no grant exists yet; after the POST
             the request is stored and the owner's trial exists, started by the editor with pro_help used 1
        """
        from ..models import EntitlementGrant
        editor = User.objects.create_user(username='help_editor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        self.client.login(username='help_editor', password='pass')
        r = self.client.get(self.url)
        self.assertContains(r, 'Send request')
        self.assertContains(r, 'starts your workspace')
        self.assertFalse(EntitlementGrant.objects.exists())
        self.client.post(self.url, {'kind': 'report', 'message': 'x', 'contact_email': 'ed@example.test'})
        self.assertTrue(ProHelpRequest.objects.exists())
        grant = EntitlementGrant.objects.get(organization=self.org)
        self.assertEqual((grant.claimed_by, grant.started_by, grant.trigger), (self.owner, editor, 'pro_help'))
        self.assertEqual(grant.allowances.get(feature='pro_help').used, 1)

    def test_trial_member_submits_and_the_form_closes(self):
        """
        GIVEN a Free organisation whose live Pro trial has one pro_help request left
        WHEN an editor submits a valid request
        THEN the request is stored, the allowance reads 0 left, and the page shows the receipt and the
             "trial used" sentence instead of the form
        """
        from ..trial import claim
        claim(self.org, self.owner)
        self.client.login(username='bill_editor', password='pass')
        self.assertContains(self.client.get(self.url), 'Send request')
        r = self.client.post(self.url, {'kind': 'report', 'message': 'Need a report', 'contact_email': 'ed@example.test'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ProHelpRequest.objects.count(), 1)
        self.assertEqual(self.org.grants.get().allowances.get(feature='pro_help').used, 1)
        self.assertContains(r, 'Received.')
        self.assertContains(r, 'data-trial-state="feature_used"')
        self.assertNotContains(r, 'Send request')
        self.assertEqual(self.client.post(self.url, {'kind': 'report', 'message': 'again',
                                                     'contact_email': 'ed@example.test'}).status_code, 403)
        self.assertEqual(ProHelpRequest.objects.count(), 1)

    def test_pro_member_submits_and_mails(self):
        """
        GIVEN a Pro organisation and an editor
        WHEN they submit a report request
        THEN a row exists, both emails go out and the event is emitted
        """
        _sub(self.org)
        survey = SurveyHeader.objects.create(organization=self.org, name='park_plan')
        self.client.login(username='bill_editor', password='pass')
        self.assertContains(self.client.get(self.url), 'Send request')
        with mock.patch('billing.events.emit') as emit, \
                mock.patch('billing.tasks.send_pro_help_request.delay', side_effect=lambda pk: __import__('billing.tasks', fromlist=['x']).send_pro_help_request(pk)), \
                self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(self.url, {'kind': 'report', 'survey': survey.pk, 'message': 'Need a council report',
                                            'contact_email': 'ed@example.test'})
        self.assertEqual(r.status_code, 200)
        req = ProHelpRequest.objects.get()
        self.assertEqual((req.kind, req.survey, req.user), ('report', survey, self.editor))
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Need a council report', mail.outbox[0].body)
        self.assertEqual(emit.call_args.args[0], 'pro_help_requested')

    def test_survey_of_another_org_rejected(self):
        _sub(self.org)
        other, _ = make_org('Other Org', 'other_owner')
        foreign = SurveyHeader.objects.create(organization=other, name='foreign')
        self.client.login(username='bill_owner', password='pass')
        self.client.post(self.url, {'kind': 'analysis', 'survey': foreign.pk, 'message': 'x', 'contact_email': 'a@b.c'})
        self.assertFalse(ProHelpRequest.objects.exists())
