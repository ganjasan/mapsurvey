"""Tests for the `point-tap-to-place` capability (openspec/specs/point-tap-to-place/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from io import BytesIO
import json
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, Membership, SurveyCollaborator
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.cloning import clone_question
from survey.tests.helpers import _make_org


class TapToPlaceTest(TestCase):
    """Spec point-tap-to-place: a map click places the mark of the only geo
    question on a section, when the creator switched it on."""

    def setUp(self):
        self.org = _make_org('Tap Org')
        self.user = User.objects.create_user(username='tapper', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='taps', organization=self.org, created_by=self.user, status='published',
            available_languages=[], redirect_url='#',
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='spots', title='Spots', code='S1', is_head=True,
        )
        self.point = Question.objects.create(
            survey_section=self.section, code='PT', order_number=1, name='Where?',
            input_type='point', color='#2563eb', tap_to_place=True,
        )
        Question.objects.create(
            survey_section=self.section, code='PT_WHY', order_number=1, name='Why?',
            input_type='text_line', parent_question_id=self.point,
        )
        Question.objects.create(
            survey_section=self.section, code='AGE', order_number=2, name='Age',
            input_type='number',
        )

    def _respondent_html(self):
        return self.client.get('/surveys/taps/spots/').content.decode()

    def _login(self):
        self.client.login(username='tapper', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _edit(self, **data):
        payload = {'name': 'Where?', 'input_type': 'point', 'color': '#2563eb', 'autosave': '1'}
        payload.update(data)
        return self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.point.id}/edit/', payload)

    # ── the rule ──

    def test_rule_counts_only_top_level_geo_questions(self):
        """
        GIVEN a point question with the setting on, a sub-question and a number question
        WHEN the rule is evaluated
        THEN it is in effect; a second geo question of any geo type turns it off
        """
        from survey.question_types import section_geo_count, tap_to_place_active
        self.assertEqual(section_geo_count(self.section), 1)
        self.assertTrue(tap_to_place_active(self.point, section_geo_count(self.section)))
        Question.objects.create(survey_section=self.section, code='CL', order_number=3,
                                name='Cloud', input_type='spraycan')
        self.assertFalse(tap_to_place_active(self.point, section_geo_count(self.section)))

    def test_rule_needs_the_setting_and_a_point(self):
        """
        GIVEN the only geo question on a section
        WHEN its setting is off, or it is a line with the flag set
        THEN the rule is not in effect
        """
        from survey.question_types import tap_to_place_active
        self.point.tap_to_place = False
        self.assertFalse(tap_to_place_active(self.point, 1))
        self.point.tap_to_place = True
        self.point.input_type = 'line'
        self.assertFalse(tap_to_place_active(self.point, 1))

    def test_default_is_off(self):
        """
        GIVEN a point question created without touching the setting
        WHEN it is read back
        THEN tap_to_place is false
        """
        q = Question.objects.create(survey_section=self.section, code='P2', name='Other', input_type='point')
        self.assertFalse(q.tap_to_place)

    # ── respondent page ──

    def test_respondent_button_carries_the_mark_and_the_hint(self):
        """
        GIVEN the only geo question on the section with the setting on
        WHEN the respondent opens the section
        THEN the point button carries data-tap-to-place and the hint is shown
        """
        html = self._respondent_html()
        self.assertIn('data-tap-to-place="1"', html)
        self.assertIn('Tap the map to mark a place', html)

    def test_second_geo_question_removes_the_mark(self):
        """
        GIVEN the setting on and a second geo question on the same section
        WHEN the respondent opens the section
        THEN neither the mark nor the hint is rendered
        """
        Question.objects.create(survey_section=self.section, code='LN', order_number=3,
                                name='Route', input_type='line')
        html = self._respondent_html()
        self.assertNotIn('data-tap-to-place="1"', html)
        self.assertNotIn('Tap the map to mark a place', html)

    def test_setting_off_renders_as_before(self):
        """
        GIVEN the setting off
        WHEN the respondent opens the section
        THEN the button has no mark and no hint
        """
        self.point.tap_to_place = False
        self.point.save(update_fields=['tap_to_place'])
        html = self._respondent_html()
        self.assertNotIn('data-tap-to-place="1"', html)
        self.assertNotIn('Tap the map to mark a place', html)

    def test_page_script_places_through_draw_created(self):
        """
        GIVEN the respondent page
        WHEN its script is inspected
        THEN the tap handler listens for clicks, is cancelled by a double-click
             and looks for the server's mark
        """
        html = self._respondent_html()
        self.assertIn("map.on('click'", html)
        self.assertIn("map.on('dblclick'", html)
        self.assertIn('button.drawpoint[data-tap-to-place]', html)

    def test_point_marks_stay_clickable_without_an_icon_class(self):
        """
        GIVEN a point question with no icon_class (the button carries data-icon="")
        WHEN the respondent page script is inspected
        THEN every new mark falls back to the default pin — L.Icon.FontAwesome
             given no class draws an empty clickable icon, leaving only the
             non-interactive shadow visible, so the mark could not be opened —
             and a tap on any pin graphic never drops a second mark
        """
        html = self._respondent_html()
        self.assertIn('data-icon=""', html)
        self.assertIn("iconClasses: iconClass || 'fas fa-map-marker-alt'", html)
        self.assertIn('.leaflet-fa-markers, .leaflet-popup', html)

    # ── editor ──

    def test_edit_saves_the_switch_in_place_on_a_live_survey(self):
        """
        GIVEN a published survey's point question with the setting on
        WHEN the creator switches it off and on again
        THEN each value is saved to the live row and no unpublished changes exist
        """
        self._login()
        self.assertEqual(self._edit().status_code, 200)
        self.point.refresh_from_db()
        self.assertFalse(self.point.tap_to_place)
        self._edit(tap_to_place='on')
        self.point.refresh_from_db()
        self.assertTrue(self.point.tap_to_place)
        self.survey.refresh_from_db()
        self.assertFalse(self.survey.has_draft_copy())

    def test_non_point_types_store_it_off(self):
        """
        GIVEN the create endpoint
        WHEN a line question is posted with tap_to_place=on
        THEN it is stored off
        """
        self._login()
        self.survey.status = 'draft'
        self.survey.save(update_fields=['status'])
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Route', 'input_type': 'line', 'color': '#000000', 'tap_to_place': 'on'},
        )
        q = Question.objects.get(survey_section=self.section, name='Route')
        self.assertFalse(q.tap_to_place)

    def test_badge_greys_out_when_not_in_effect(self):
        """
        GIVEN the setting on
        WHEN the question row renders alone, and with a second geo question present
        THEN the badge is active first and greyed out (with the reason) second
        """
        from django.template.loader import render_to_string
        ctx = {'question': self.point, 'survey': self.survey}
        html = render_to_string('editor/partials/question_list_item.html', ctx)
        self.assertIn('tap-to-place-badge', html)
        self.assertNotIn('tap-to-place-badge--off', html)
        Question.objects.create(survey_section=self.section, code='PG', order_number=3,
                                name='Area', input_type='polygon')
        html = render_to_string('editor/partials/question_list_item.html', ctx)
        self.assertIn('tap-to-place-badge--off', html)
        self.assertIn('Another map question is on this page', html)

    # ── persistence ──

    def _export(self):
        from survey.serialization import export_survey_to_zip
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        return buf

    def test_zip_round_trip_keeps_the_setting(self):
        """
        GIVEN a survey whose point question has the setting on
        WHEN it is exported and imported back
        THEN the imported point question has the setting on
        """
        from survey.serialization import import_survey_from_zip
        buf = self._export()
        with zipfile.ZipFile(buf) as z:
            data = json.loads(z.read('survey.json'))
        q = next(q for q in data['survey']['sections'][0]['questions'] if q['code'] == 'PT')
        self.assertIs(q['tap_to_place'], True)
        buf.seek(0)
        imported, _warnings = import_survey_from_zip(buf, organization=self.org)
        new_q = Question.objects.get(survey_section__survey_header=imported, input_type='point')
        self.assertTrue(new_q.tap_to_place)

    def test_old_archive_imports_it_off(self):
        """
        GIVEN an archive whose questions carry no tap_to_place key
        WHEN it is imported
        THEN the point question has the setting off
        """
        from survey.serialization import import_survey_from_zip
        buf = self._export()
        with zipfile.ZipFile(buf) as z:
            data = json.loads(z.read('survey.json'))
            others = {n: z.read(n) for n in z.namelist() if n != 'survey.json'}
        for q in data['survey']['sections'][0]['questions']:
            q.pop('tap_to_place', None)
        out = BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr('survey.json', json.dumps(data))
            for n, b in others.items():
                z.writestr(n, b)
        out.seek(0)
        imported, _warnings = import_survey_from_zip(out, organization=self.org)
        new_q = Question.objects.get(survey_section__survey_header=imported, input_type='point')
        self.assertFalse(new_q.tap_to_place)

    def test_clone_keeps_the_setting(self):
        """
        GIVEN a point question with the setting on
        WHEN it is cloned into another section
        THEN the copy has the setting on
        """
        from survey.cloning import clone_question
        other = SurveySection.objects.create(survey_header=self.survey, name='s2', title='Two', code='S2')
        copy = clone_question(self.point, target_section=other)
        self.assertTrue(copy.tap_to_place)
