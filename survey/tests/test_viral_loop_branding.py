"""Tests for the `viral-loop-branding` capability (openspec/specs/viral-loop-branding/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from survey.models import SurveyHeader, SurveySection
from survey.serialization import serialize_survey_to_dict
from survey.tests.helpers import _make_org


class ViralLoopBrandingTest(TestCase):
    """"Made with Mapsurvey" acquisition loop on public survey + thanks pages."""

    def setUp(self):
        self.org = _make_org("ViralOrg")
        self.survey = SurveyHeader.objects.create(name="viral_s", organization=self.org,
                                                  status="published", visibility="public")
        SurveySection.objects.create(name="s1", survey_header=self.survey, is_head=True)

    def test_default_show_branding_is_true(self):
        """
        GIVEN a newly created survey
        WHEN show_branding is not set
        THEN it defaults to True (free-tier loop on by default)
        """
        self.assertTrue(self.survey.show_branding)

    def test_badge_and_utm_on_thanks_when_enabled(self):
        """
        GIVEN a public survey with branding on
        WHEN the thanks page is rendered
        THEN it shows the CTA linking to registration tagged utm_source=viral_loop&medium=thanks
        """
        resp = Client().get(f"/surveys/{self.survey.name}/thanks/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Made with")
        self.assertContains(resp, "utm_source=viral_loop")
        self.assertContains(resp, "utm_medium=thanks")

    def test_badge_on_survey_section_when_enabled(self):
        """
        GIVEN a public survey with branding on
        WHEN a section page is rendered
        THEN the CTA appears with utm_medium=survey
        """
        resp = Client().get(f"/surveys/{self.survey.name}/s1/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Made with")
        self.assertContains(resp, "utm_medium=survey")

    def test_badge_mandatory_even_when_flag_off(self):
        """
        GIVEN a survey with show_branding turned off (a future paid-tier flag)
        WHEN the thanks page is rendered
        THEN the CTA is STILL shown — branding is mandatory for the free tier
        """
        self.survey.show_branding = False
        self.survey.save(update_fields=["show_branding"])
        resp = Client().get(f"/surveys/{self.survey.name}/thanks/")
        self.assertContains(resp, "Made with")

    def test_serialization_includes_show_branding(self):
        """
        GIVEN a survey with branding off
        WHEN it is serialized
        THEN show_branding is exported
        """
        from survey.serialization import serialize_survey_to_dict
        self.survey.show_branding = False
        self.survey.save(update_fields=["show_branding"])
        self.assertEqual(serialize_survey_to_dict(self.survey)["show_branding"], False)


class BrandingSwitchInSettingsPanelTest(TestCase):
    """The badge switch stays on its own row in the Build "Survey settings" panel."""

    def test_switch_is_not_pulled_out_of_its_row(self):
        """
        GIVEN the survey owner opens the Build "Survey settings" panel
        WHEN the badge checkbox renders inside its .pr-field label with Bootstrap's
             position:absolute .form-check-input class
        THEN editor_base resets that class to position:static, so the checkbox does not
             stay behind while the panel scrolls and float over the Survey period card
        """
        from pathlib import Path
        from django.conf import settings
        from django.contrib.auth.models import User
        from survey.models import Membership

        owner = User.objects.create_user('brand_owner', password='pass')
        org = _make_org("BrandPanelOrg")
        Membership.objects.create(user=owner, organization=org, role='owner')
        survey = SurveyHeader.objects.create(name="brand_panel", organization=org, created_by=owner)
        SurveySection.objects.create(name="s1", survey_header=survey, is_head=True)

        client = Client()
        client.login(username='brand_owner', password='pass')
        panel = client.get(f'/editor/surveys/{survey.uuid}/settings-panel/').content.decode()
        self.assertRegex(panel, r'<label[^>]*>\s*<input[^>]*class="form-check-input"[^>]*id="id_show_branding"')

        base = (Path(settings.BASE_DIR) / 'survey/templates/editor/editor_base.html').read_text()
        self.assertIn('.pr-field label > .form-check-input { position: static; margin: 0; }', base)
