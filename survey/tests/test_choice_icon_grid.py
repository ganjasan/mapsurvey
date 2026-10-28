"""Tests for the `choice-icon-grid` capability (openspec/specs/choice-icon-grid/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from io import BytesIO
import json
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.forms import SurveySectionAnswerForm
from survey import marker_icons as _marker_icons
from survey.tests.helpers import _make_org


class ChoiceIconGridTest(TestCase):
    """The icon grid display style (spec choice-icon-grid) and its choice extras
    (spec inline-choices): rendering on every respondent surface, the one
    display-style table, editor save and preview, ZIP round-trip."""

    KINDS = [
        {"code": 1, "name": "Park", "icon": "maki:park", "group": "Nature"},
        {"code": 2, "name": "Tree", "icon": "maki:not-a-real-icon", "group": "Nature"},
        {"code": 3, "name": "Swings", "icon": "fas fa-child", "group": "Play"},
        {"code": 4, "name": "Bench", "group": "<b>Services</b>"},
        {"code": 5, "name": "Other", "other": True, "group": "<b>Services</b>"},
    ]

    def setUp(self):
        self.org = _make_org('IconGridOrg')
        self.user = User.objects.create_user('gridowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='icon_grid_survey', organization=self.org, created_by=self.user,
            status='published', redirect_url='/thanks/', available_languages=['en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.q_kind = Question.objects.create(
            survey_section=self.section, name='Kind of place', code='Q_KIND',
            input_type='choice', order_number=1, choices=self.KINDS, display_style='icon_grid',
        )
        self.q_multi = Question.objects.create(
            survey_section=self.section, name='What is there?', code='Q_MULTI',
            input_type='multichoice', order_number=2, display_style='icon_grid',
            choices=[{"code": 1, "name": "Bench", "icon": "temaki:bench"},
                     {"code": 2, "name": "Tree", "icon": "maki:park"}],
        )
        self.url = f'/surveys/{self.survey.uuid}/{self.section.name}/'

    def _start(self):
        self.client.get(f'/surveys/{self.survey.uuid}/')
        return self.client.get(self.url).content.decode()

    def _login_editor(self):
        self.survey.status = 'draft'
        self.survey.save()
        self.client.login(username='gridowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    # ── one display-style table ──

    def test_style_table_drives_every_resolver(self):
        """
        GIVEN the display-style table
        WHEN styles are resolved for each type
        THEN icon_grid is accepted on choice and multichoice only, and dropdown stays choice-only
        """
        from survey.question_types import allowed_display_styles
        self.assertIn('icon_grid', allowed_display_styles('choice'))
        self.assertIn('icon_grid', allowed_display_styles('multichoice'))
        self.assertNotIn('dropdown', allowed_display_styles('multichoice'))
        self.assertEqual(allowed_display_styles('text'), ('default',))
        self.assertEqual(SurveySectionAnswerForm.resolve_display_style(self.q_multi, 'scale_strip'), 'icon_grid')
        text_q = Question(input_type='text', display_style='icon_grid')
        self.assertEqual(SurveySectionAnswerForm.resolve_display_style(text_q, 'scale_strip'), 'default')
        multi_dd = Question(input_type='multichoice', display_style='dropdown')
        self.assertEqual(SurveySectionAnswerForm.resolve_display_style(multi_dd, 'scale_strip'), 'default')

    def test_editor_form_keeps_icon_grid_and_drops_it_elsewhere(self):
        """
        GIVEN the question form submitted with display_style icon_grid
        WHEN it is validated for multichoice, choice and text
        THEN choice and multichoice keep icon_grid and text falls back to default
        """
        from survey.editor_forms import QuestionForm
        base = {'name': 'Pick', 'subtext': '', 'color': '#000000', 'icon_class': '', 'display_style': 'icon_grid'}
        for input_type, expected in (('multichoice', 'icon_grid'), ('choice', 'icon_grid'), ('text', 'default')):
            form = QuestionForm(dict(base, input_type=input_type))
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['display_style'], expected, input_type)

    # ── choice extras ──

    def test_normalise_choice_extras(self):
        """
        GIVEN choices with padded, blank, non-string and over-long icon/group values
        WHEN they are normalised
        THEN values are trimmed and capped, blanks and non-strings dropped, other keys and order kept
        """
        from survey.question_types import normalise_choice_extras
        choices = [
            {"code": 2, "name": "B", "icon": "  maki:park ", "group": " Nature ", "other": True},
            {"code": 1, "name": "A", "icon": "", "group": 7},
            {"code": 3, "name": "C", "group": "x" * 100},
            "junk",
        ]
        out = normalise_choice_extras(choices)
        self.assertEqual(out[0], {"code": 2, "name": "B", "icon": "maki:park", "group": "Nature", "other": True})
        self.assertEqual(out[1], {"code": 1, "name": "A"})
        self.assertEqual(len(out[2]["group"]), 60)
        self.assertEqual(out[3], "junk")

    def test_editor_save_stores_extras_only_when_set(self):
        """
        GIVEN the question modal posting choices with an icon/group on one row and blanks on another
        WHEN a new multichoice question is created with display_style icon_grid
        THEN the first entry carries icon and group, the second carries neither
        """
        self._login_editor()
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Amenities', 'input_type': 'multichoice', 'color': '#000000',
             'display_style': 'icon_grid',
             'choices_json': json.dumps([
                 {"code": 1, "name": "Bench", "icon": " temaki:bench ", "group": "Rest"},
                 {"code": 2, "name": "Bin", "icon": "", "group": "  "},
             ])},
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Amenities')
        self.assertEqual(q.display_style, 'icon_grid')
        self.assertEqual(q.choices, [
            {"code": 1, "name": "Bench", "icon": "temaki:bench", "group": "Rest"},
            {"code": 2, "name": "Bin"},
        ])

    def test_marker_icons_is_drawable(self):
        """
        GIVEN icon values of every form
        WHEN asked whether a tile may draw them
        THEN catalogued map-set names and Font Awesome classes are drawable, unknown names and blanks are not
        """
        self.assertTrue(_marker_icons.is_drawable('maki:park'))
        self.assertTrue(_marker_icons.is_drawable('fas fa-child'))
        self.assertFalse(_marker_icons.is_drawable('maki:not-a-real-icon'))
        self.assertFalse(_marker_icons.is_drawable(''))
        self.assertFalse(_marker_icons.is_drawable('   '))

    # ── respondent rendering ──

    def test_grid_renders_tiles_groups_and_icons(self):
        """
        GIVEN an icon-grid choice question with three groups, a known, an unknown and a missing icon
        WHEN the section is rendered
        THEN one tile per option appears in order under three escaped headings, the known icons
             render through the marker-icon helper and the unknown one renders nothing
        """
        html = self._start()
        self.assertIn('data-choice-icon-grid data-cig-collapse', html)
        self.assertEqual(html.count('class="cig-tile__input"'), 5 + 2)
        self.assertIn('<div class="cig-run__title">Nature</div>', html)
        self.assertIn('<div class="cig-run__title">Play</div>', html)
        self.assertIn('<div class="cig-run__title">&lt;b&gt;Services&lt;/b&gt;</div>', html)
        self.assertNotIn('<b>Services</b>', html)
        self.assertIn('#maki-park"', html)
        self.assertIn('fas fa-child', html)
        self.assertNotIn('maki-not-a-real-icon', html)
        self.assertLess(html.index('value="1" class="cig-tile__input"'), html.index('value="4" class="cig-tile__input"'))
        self.assertIn('Show all options', html)
        self.assertRegex(html, r'js/choice_icon_grid(\.[0-9a-f]+)?\.js')

    def test_flat_grid_and_multichoice_never_collapses(self):
        """
        GIVEN an icon-grid multichoice question whose options have no group
        WHEN the section is rendered
        THEN its tiles are checkboxes in one untitled run and the grid carries no collapse marker
        """
        html = self._start()
        self.assertEqual(html.count('type="checkbox" name="Q_MULTI"'), 2)
        self.assertEqual(html.count('data-choice-icon-grid'), 2)
        # Only the single-choice grid folds.
        self.assertEqual(html.count('data-cig-collapse'), 1)
        self.assertEqual(html.count('class="cig-run__title"'), 3)

    def test_submission_stores_the_same_codes_as_the_list(self):
        """
        GIVEN the icon-grid choice and multichoice questions
        WHEN the respondent picks one tile and two tiles and submits
        THEN the answers hold exactly those codes, as a list submission would
        """
        self._start()
        self.client.post(self.url, {'Q_KIND': '3', 'Q_MULTI': ['1', '2']})
        session = SurveySession.objects.get(survey=self.survey)
        self.assertEqual(Answer.objects.get(survey_session=session, question=self.q_kind).selected_choices, [3])
        self.assertEqual(Answer.objects.get(survey_session=session, question=self.q_multi).selected_choices, [1, 2])

    def test_write_in_tile_renders_one_field_and_stores_text(self):
        """
        GIVEN an icon-grid choice question with an option flagged other
        WHEN the section renders and the respondent picks that tile with text
        THEN one write-in field renders beneath the grid and the text is stored with the answer
        """
        html = self._start()
        self.assertEqual(html.count('data-other-for="Q_KIND"'), 1)
        self.client.post(self.url, {'Q_KIND': '5', 'Q_KIND-other': ' fountain '})
        session = SurveySession.objects.get(survey=self.survey)
        answer = Answer.objects.get(survey_session=session, question=self.q_kind)
        self.assertEqual((answer.selected_choices, answer.text), ([5], 'fountain'))

    def test_required_grid_rejects_an_empty_value(self):
        """
        GIVEN a required icon-grid choice question
        WHEN its field is cleaned without a value
        THEN validation fails exactly as it would for the list
        """
        self.q_kind.required = True
        self.q_kind.save()
        field = SurveySectionAnswerForm.single_question_form(self.q_kind).fields['Q_KIND']
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            field.clean('')
        self.assertEqual(field.clean('2'), '2')

    def test_stored_answer_marks_its_tile(self):
        """
        GIVEN a single-question form bound to a stored answer
        WHEN the widget renders
        THEN the chosen tile is checked and carries the highlight class
        """
        field = SurveySectionAnswerForm.single_question_form(self.q_kind).fields['Q_KIND']
        html = field.widget.render('Q_KIND', '3', attrs={'id': 'id_Q_KIND'})
        self.assertIn('class="cig-tile cig-tile--on"', html)
        self.assertRegex(html, r'value="3" class="cig-tile__input"[^>]*checked')

    def test_grid_in_a_geo_popup(self):
        """
        GIVEN an icon-grid choice that is a sub-question of a point question
        WHEN the section is rendered
        THEN the pop-up form carries the grid, and the pop-up init repaints grids after restoring values
        """
        point = Question.objects.create(
            survey_section=self.section, name='Spot', code='Q_SPOT', input_type='point', order_number=3,
        )
        Question.objects.create(
            survey_section=self.section, name='Type', code='S_TYPE', input_type='choice', order_number=1,
            parent_question_id=point, display_style='icon_grid',
            choices=[{"code": 1, "name": "Park", "icon": "maki:park"}, {"code": 2, "name": "Shop"}],
        )
        html = self._start()
        # Pop-up forms ride in the page as JSON-escaped strings.
        self.assertIn('name=\\"S_TYPE\\" value=\\"1\\" class=\\"cig-tile__input\\"', html)
        self.assertIn('window.syncIconGrids(root)', html)

    def test_live_preview_renders_the_grid(self):
        """
        GIVEN an unsaved multichoice draft with icon_grid and icons
        WHEN the modal posts it to the live preview endpoint
        THEN the frame shows the tiles and loads the grid script
        """
        self._login_editor()
        response = self.client.post(
            reverse('editor_question_preview_live', args=[self.survey.uuid, self.section.id]),
            {'input_type': 'multichoice', 'name': 'Which?', 'display_style': 'icon_grid',
             'choices_json': json.dumps([{"code": 1, "name": "Park", "icon": "maki:park", "group": "Nature"}])},
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-choice-icon-grid', html)
        self.assertIn('<div class="cig-run__title">Nature</div>', html)
        self.assertIn('#maki-park"', html)
        self.assertRegex(html, r'js/choice_icon_grid(\.[0-9a-f]+)?\.js')

    # ── icon colour (change icon-grid-color-picker) ──

    def test_normaliser_keeps_only_hex_colours(self):
        """
        GIVEN choices with a padded upper-case hex, a colour name and a blank colour
        WHEN they are normalised
        THEN the hex is kept lower-cased and the others are dropped
        """
        from survey.question_types import normalise_choice_extras
        out = normalise_choice_extras([
            {"code": 1, "name": "A", "color": " #DC2626 "},
            {"code": 2, "name": "B", "color": "red"},
            {"code": 3, "name": "C", "color": ""},
        ])
        self.assertEqual(out, [
            {"code": 1, "name": "A", "color": "#dc2626"},
            {"code": 2, "name": "B"},
            {"code": 3, "name": "C"},
        ])

    def _tile_html(self, question):
        field = SurveySectionAnswerForm.single_question_form(question).fields[question.code]
        return field.widget.render(question.code, None, attrs={'id': 'id_' + question.code})

    def test_question_colour_paints_every_icon_and_option_colour_wins(self):
        """
        GIVEN an icon-grid question coloured #16a34a whose Swings option is coloured #dc2626
        WHEN the grid renders
        THEN the sprite icon is filled with the question colour and the Swings glyph carries its own
        """
        self.q_kind.color = '#16a34a'
        self.q_kind.choices = [dict(c) for c in self.KINDS]
        self.q_kind.choices[2]['color'] = '#dc2626'
        self.q_kind.save()
        html = self._tile_html(self.q_kind)
        self.assertIn('fill:#16a34a;', html)
        self.assertRegex(html, r'fas fa-child[^>]*color:#dc2626;')

    def test_default_question_colour_emits_no_inline_colour(self):
        """
        GIVEN an icon-grid question left on the model default colour #000000 with no option colours
        WHEN the grid renders
        THEN no icon carries an inline colour, so the CSS grey applies
        """
        self.assertEqual(self.q_kind.color, '#000000')
        html = self._tile_html(self.q_kind)
        self.assertIn('fill:currentColor;', html)
        self.assertNotIn('color:#000000', html)

    def test_editor_save_normalises_option_colour(self):
        """
        GIVEN the modal posting a choice with an upper-case colour and one with garbage
        WHEN a new icon-grid choice question is created
        THEN the first keeps the lower-cased colour and the second stores none
        """
        self._login_editor()
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Coloured', 'input_type': 'choice', 'color': '#000000', 'display_style': 'icon_grid',
             'choices_json': json.dumps([{"code": 1, "name": "A", "color": "#ABCDEF"},
                                         {"code": 2, "name": "B", "color": "javascript:alert(1)"}])},
        )
        q = Question.objects.get(survey_section=self.section, name='Coloured')
        self.assertEqual(q.choices, [{"code": 1, "name": "A", "color": "#abcdef"}, {"code": 2, "name": "B"}])

    def test_modal_has_colour_column_and_wide_picker(self):
        """
        GIVEN the question modal for an icon-grid question
        WHEN it is rendered inside the editor
        THEN the choices table has the Color column, the Color field is gated on the grid,
             and the picker is one button opening a fixed-position panel sized on its own
             (change icon-picker-one-button)
        """
        self._login_editor()
        html = self.client.get(reverse('editor_question_edit', args=[self.survey.uuid, self.q_multi.id])).content.decode()
        self.assertIn('class="choice-grid-cell choice-color-cell"', html)
        self.assertIn("show('fg-color', isGeo || isStars || isGrid);", html)
        # The row's icon input is a bare value carrier now, not a styled text field.
        self.assertIn('<input type="text" class="choice-icon">', html)
        self.assertIn("remove: '", html)
        page = self.client.get(f'/editor/surveys/{self.survey.uuid}/').content.decode()
        self.assertIn('.icon-picker-trigger {', page)
        self.assertIn('width: min(560px, calc(100vw - 16px));', page)
        self.assertIn('position: fixed;', page[page.index('.icon-picker-dropdown {'):][:200])

    def test_modal_offers_icon_grid_for_multichoice(self):
        """
        GIVEN the question modal for an icon-grid question
        WHEN it is rendered
        THEN the Icon grid card is scoped to choice and multichoice, the List card covers multichoice,
             and the choices table has the Icon and Group columns
        """
        self._login_editor()
        response = self.client.get(
            reverse('editor_question_edit', args=[self.survey.uuid, self.q_multi.id]),
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-types="choice multichoice"', html)
        self.assertIn('value="icon_grid"', html)
        self.assertIn('class="choice-grid-cell"', html)
        self.assertIn("var DISPLAY_STYLE_TYPES = ['rating', 'choice', 'multichoice'];", html)

    # ── serialization ──

    def _roundtrip(self):
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode="structure")
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
        survey_json["survey"]["name"] = "icon_grid_imported"
        out = BytesIO()
        with zipfile.ZipFile(out, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        out.seek(0)
        imported, _ = import_survey_from_zip(out)
        return imported

    def test_zip_round_trip_keeps_style_icons_and_groups(self):
        """
        GIVEN icon-grid choice and multichoice questions whose choices carry icon and group
        WHEN the survey is exported and re-imported
        THEN both keep display_style icon_grid and identical choice entries
        """
        imported = self._roundtrip()
        kind = Question.objects.get(survey_section__survey_header=imported, name='Kind of place')
        multi = Question.objects.get(survey_section__survey_header=imported, name='What is there?')
        self.assertEqual((kind.display_style, kind.choices), ('icon_grid', self.KINDS))
        self.assertEqual((multi.display_style, multi.choices), ('icon_grid', self.q_multi.choices))

    def test_pre_change_archive_imports_unchanged(self):
        """
        GIVEN a survey with plain, dropdown and rating questions that never used the grid
        WHEN it is exported and re-imported
        THEN every display_style and choices list is unchanged
        """
        self.q_kind.delete()
        self.q_multi.delete()
        plain = [{"code": 1, "name": "A"}, {"code": 2, "name": "B", "other": True}]
        Question.objects.create(survey_section=self.section, name='Plain', code='Q_P', input_type='choice',
                                order_number=1, choices=plain)
        Question.objects.create(survey_section=self.section, name='Drop', code='Q_D', input_type='choice',
                                order_number=2, choices=plain, display_style='dropdown')
        Question.objects.create(survey_section=self.section, name='Rate', code='Q_R', input_type='rating',
                                order_number=3, choices=plain[:1], display_style='stars')
        imported = self._roundtrip()
        got = {q.name: (q.display_style, q.choices)
               for q in Question.objects.filter(survey_section__survey_header=imported)}
        self.assertEqual(got, {
            'Plain': ('default', plain), 'Drop': ('dropdown', plain), 'Rate': ('stars', plain[:1]),
        })
