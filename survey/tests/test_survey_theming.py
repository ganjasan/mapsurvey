"""Tests for the `survey-theming` capability (openspec/specs/survey-theming/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.models import Organization, SurveyHeader
from survey.editor_forms import SurveyHeaderForm


class SurveyThemingFormTest(TestCase):
    """Accent color persisted through SurveyHeaderForm into style_settings."""

    def _data(self, **overrides):
        data = {
            'name': 'themed_survey',
            'redirect_url': '#',
            'available_languages': '["en"]',
            'visibility': 'private',
            'basemaps': '["streets"]',
            'default_basemap': 'streets',
        }
        data.update(overrides)
        return data

    def setUp(self):
        self.org = Organization.objects.create(name="Theming Org")
        self.survey = SurveyHeader.objects.create(
            name='themed_survey', organization=self.org,
        )

    def test_accent_saved_when_enabled(self):
        """
        GIVEN the settings form with the accent checkbox on and a valid hex
        WHEN the form is saved
        THEN style_settings carries the accent color
        """
        from survey.editor_forms import SurveyHeaderForm
        form = SurveyHeaderForm(
            self._data(use_accent_color='on', accent_color='#7a1f2b'),
            instance=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.get_accent_color(), '#7a1f2b')

    def test_accent_removed_when_disabled(self):
        """
        GIVEN a survey with a stored accent and the checkbox submitted off
        WHEN the form is saved
        THEN the accent key is removed from style_settings
        """
        self.survey.style_settings = {'accent_color': '#7a1f2b'}
        self.survey.save()
        from survey.editor_forms import SurveyHeaderForm
        form = SurveyHeaderForm(
            self._data(accent_color='#7a1f2b'),
            instance=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.survey.refresh_from_db()
        self.assertIsNone(self.survey.get_accent_color())

    def test_invalid_hex_rejected(self):
        """
        GIVEN the accent checkbox on and a malformed color
        WHEN the form is validated
        THEN validation fails on accent_color
        """
        from survey.editor_forms import SurveyHeaderForm
        form = SurveyHeaderForm(
            self._data(use_accent_color='on', accent_color='red'),
            instance=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('accent_color', form.errors)

    def test_import_cleaner_keeps_valid_accent_and_drops_junk(self):
        """
        GIVEN imported style_settings with a valid accent and a junk value
        WHEN _clean_style_settings runs
        THEN the valid hex survives and anything else is dropped
        """
        from survey.serialization import _clean_style_settings

        self.assertEqual(
            _clean_style_settings({'accent_color': '#00AAff'}),
            {'accent_color': '#00AAff'},
        )
        self.assertEqual(_clean_style_settings({'accent_color': 'url(x)'}), {})
