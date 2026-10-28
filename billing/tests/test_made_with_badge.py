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


@override_settings(**PPG_SETTINGS)
class BrandingTrialTest(TestCase):
    """The badge under a Pro trial (change pro-trial-allowances): one switch-off, counted in the service."""

    DATA = {'redirect_url': '#', 'visibility': 'private', 'basemaps': '["streets"]', 'default_basemap': 'streets'}

    def setUp(self):
        from ..trial import claim
        self.org, self.owner = make_org()
        self.a = SurveyHeader.objects.create(organization=self.org, name='survey_a')
        self.b = SurveyHeader.objects.create(organization=self.org, name='survey_b')
        self.grant = claim(self.org, self.owner)

    def _save(self, survey, show_branding):
        from survey.services import surveys as svc
        from survey.services.context import Actor
        survey.refresh_from_db()
        data = dict(self.DATA, name=survey.name)
        if show_branding:
            data['show_branding'] = 'on'
        ents.forget(survey.organization)
        return svc.update_settings(Actor(user=self.owner), survey, data)

    def _used(self):
        return self.grant.allowances.get(feature='unbranded').used

    def test_one_switch_off_then_refused(self):
        """
        GIVEN a Free workspace whose live trial allows one unbranded survey
        WHEN the badge is switched off on survey A, then on survey B
        THEN A is stored unbranded and the allowance is spent; B's save keeps the badge and spends nothing
        """
        self._save(self.a, False)
        self.a.refresh_from_db()
        self.assertFalse(self.a.show_branding)
        self.assertEqual(self._used(), 1)
        self._save(self.b, False)   # the switch is disabled now: the value is ignored, not an error
        self.b.refresh_from_db()
        self.assertTrue(self.b.show_branding)
        self.assertEqual(self._used(), 1)

    def test_exhausted_between_render_and_save_is_a_field_error(self):
        """
        GIVEN two settings forms built while one switch-off was left (two tabs)
        WHEN both switch the badge off
        THEN the first is stored, the second raises ValidationFailed on show_branding and keeps the badge
        """
        from survey.services import surveys as svc
        from survey.services.context import Actor
        from survey.services.errors import ValidationFailed
        ents.forget(self.org)
        self.b.refresh_from_db()
        stale = SurveyHeaderForm(dict(self.DATA, name=self.b.name), instance=self.b)
        self.assertFalse(stale.fields['show_branding'].disabled)
        self._save(self.a, False)
        with mock.patch.object(svc, 'bind', return_value=stale), self.assertRaises(ValidationFailed) as cm:
            svc.update_settings(Actor(user=self.owner), self.b, {})
        self.assertIn('show_branding', cm.exception.fields)
        self.b.refresh_from_db()
        self.assertTrue(self.b.show_branding)
        self.assertEqual(self._used(), 1)

    def test_switch_back_on_refunds_nothing(self):
        """
        GIVEN survey A was switched off under the trial, spending its only switch-off
        WHEN A's badge is switched back on
        THEN A stores the badge, the allowance still reads 1 used, and B's form keeps the switch disabled
        """
        self._save(self.a, False)
        self._save(self.a, True)
        self.a.refresh_from_db()
        self.assertTrue(self.a.show_branding)
        self.assertEqual(self._used(), 1)
        ents.forget(self.org)
        self.b.refresh_from_db()
        self.assertTrue(SurveyHeaderForm(instance=self.b).fields['show_branding'].disabled)

    def test_already_off_survey_can_turn_badge_back_on_after_exhaustion(self):
        """
        GIVEN survey A is unbranded and the trial's switch-off is spent
        WHEN A's settings form is built and saved unchecked again
        THEN the switch is enabled (so the badge can be turned back on) and nothing more is spent
        """
        self._save(self.a, False)
        self.a.refresh_from_db()
        ents.forget(self.org)
        self.assertFalse(SurveyHeaderForm(instance=self.a).fields['show_branding'].disabled)
        self._save(self.a, False)
        self.assertEqual(self._used(), 1)

    def test_pro_switch_off_spends_nothing(self):
        """
        GIVEN a workspace that is Pro and also holds a live trial
        WHEN the badge is switched off on two surveys
        THEN both are stored unbranded and the allowance is untouched
        """
        _sub(self.org)
        self._save(self.a, False)
        self._save(self.b, False)
        self.assertEqual(self._used(), 0)

    def test_badge_returns_when_the_trial_expires(self):
        """
        GIVEN survey A was switched unbranded during the trial
        WHEN the trial's expires_at passes
        THEN the badge renders again on the next request, with no data change
        """
        self._save(self.a, False)
        self.a.refresh_from_db()
        t = Template('{% include "partials/_made_with_mapsurvey.html" with medium="thanks" %}')
        ents.forget(self.org)
        self.a.organization = self.org
        self.assertNotIn('made-with-mapsurvey', t.render(Context({'survey': self.a})))
        type(self.grant).objects.filter(pk=self.grant.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        ents.forget(self.org)
        self.assertIn('made-with-mapsurvey', t.render(Context({'survey': self.a})))
        self.a.refresh_from_db()
        self.assertFalse(self.a.show_branding)
