"""Tests for the `made-with-badge` capability.

Spec: openspec/changes/paywall-payproglobal/specs/made-with-badge/spec.md
(after archive: openspec/specs/made-with-badge/spec.md). One module per capability -- see #273.
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
class BrandingGateTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.survey = SurveyHeader.objects.create(organization=self.org, name='badge_survey')

    def _badge(self):
        t = Template('{% include "partials/_made_with_mapsurvey.html" with medium="thanks" %}')
        self.org._entitlements = None
        self.survey.organization = self.org
        return 'made-with-mapsurvey' in t.render(Context({'survey': self.survey}))

    def test_free_always_renders(self):
        self.survey.show_branding = False
        self.assertTrue(self._badge())

    def test_pro_off_hides_everywhere(self):
        _sub(self.org)
        self.survey.show_branding = False
        self.assertFalse(self._badge())
        self.survey.show_branding = True
        self.assertTrue(self._badge())

    def test_lapse_restores_badge(self):
        s = _sub(self.org)
        self.survey.show_branding = False
        self.assertFalse(self._badge())
        s.current_period_end = timezone.now() - timedelta(days=1)
        s.save()
        self.assertTrue(self._badge())

    def test_settings_form_ignores_value_without_entitlement(self):
        """
        GIVEN a Free organisation's survey with show_branding=True
        WHEN the settings form is submitted with show_branding unchecked
        THEN the stored value stays True; a Pro organisation's form stores False
        """
        data = {'name': 'badge_survey', 'redirect_url': '#', 'visibility': 'private', 'basemaps': '["streets"]',
                'default_basemap': 'streets'}
        form = SurveyHeaderForm(data, instance=self.survey)
        self.assertTrue(form.fields['show_branding'].disabled)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.save().show_branding)
        _sub(self.org)
        self.survey.organization._entitlements = None
        form = SurveyHeaderForm(data, instance=self.survey)
        self.assertFalse(form.fields['show_branding'].disabled)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().show_branding)
