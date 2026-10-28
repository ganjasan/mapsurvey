"""Tests for the `rating-question-display` capability (openspec/specs/rating-question-display/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, Client
from django.contrib.auth.models import User
from io import BytesIO
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.tests.helpers import _make_org


class StarRatingDisplayTest(TestCase):
    """The star display style for rating questions (change star-rating-display)."""

    def setUp(self):
        self.org = _make_org('StarOrg')
        self.user = User.objects.create_user('staruser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.choices = [{"code": i, "name": {"en": name}} for i, name in
                        enumerate(['awful', 'poor', 'ok', 'good', 'great'], start=1)]

    def _survey(self, display_style='stars', survey_default='scale_strip',
                color='#000000', icon_class='', choices='use-default'):
        survey = SurveyHeader.objects.create(
            name=f'stars_{display_style}_{color}_{id(self)}', organization=self.org,
            created_by=self.user, status='published',
            style_settings={'rating_display_style': survey_default},
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='s1', code='S1', is_head=True,
        )
        question = Question.objects.create(
            survey_section=section, name='How was it?', code='q_rate',
            input_type='rating', order_number=1, display_style=display_style,
            color=color, icon_class=icon_class,
            choices=self.choices if choices == 'use-default' else choices,
        )
        self.client = Client()
        return survey, section, question

    def _get(self, survey):
        return self.client.get(f'/surveys/{survey.uuid}/s1/')

    def test_untouched_question_renders_gold_stars(self):
        """
        GIVEN a rating question set to stars whose colour and icon were never set
        WHEN a respondent opens the section
        THEN it renders solid stars in gold, one per choice
        """
        survey, _section, _q = self._survey()

        content = self._get(survey).content.decode()

        self.assertIn('rating-stars', content)
        self.assertIn('--star-color: #f5b301', content)
        self.assertEqual(content.count('rating-stars__star'), 5)
        self.assertEqual(content.count('fas fa-star'), 5)

    def test_creator_icon_and_colour_reach_the_render(self):
        """
        GIVEN a star rating whose creator picked a heart and a red colour
        WHEN a respondent opens the section
        THEN the question renders red hearts rather than gold stars
        """
        survey, _section, _q = self._survey(color='#d9534f', icon_class='fas fa-heart')

        content = self._get(survey).content.decode()

        self.assertIn('--star-color: #d9534f', content)
        self.assertEqual(content.count('fas fa-heart'), 5)
        self.assertNotIn('#f5b301', content)

    def test_choice_names_are_available_to_assistive_technology(self):
        """
        GIVEN a star rating with named choices
        WHEN it renders
        THEN every choice name is present as text, not only as an icon
        """
        survey, _section, _q = self._survey()

        content = self._get(survey).content.decode()

        for name in ('awful', 'poor', 'ok', 'good', 'great'):
            self.assertIn(name, content)

    def test_stars_are_rendered_in_reverse_dom_order(self):
        """
        GIVEN the star partial, whose CSS fill depends on reversed DOM order
        WHEN it renders
        THEN the last choice appears before the first in the markup

        Pinned because the template loop and the CSS sibling selector are one
        mechanism split across two files: reversing the loop alone, or dropping
        the reversal, silently breaks the fill.
        """
        survey, _section, _q = self._survey()

        content = self._get(survey).content.decode()

        self.assertLess(content.index('great'), content.index('awful'))

    def test_survey_wide_default_applies_to_an_unset_question(self):
        """
        GIVEN a survey whose default rating style is stars
        WHEN a rating question with no style of its own renders
        THEN it renders as stars
        """
        survey, _section, _q = self._survey(display_style='default', survey_default='stars')

        self.assertIn('rating-stars', self._get(survey).content.decode())

    def test_storage_is_identical_across_styles(self):
        """
        GIVEN the same rating question rendered as stars and as a compact strip
        WHEN a respondent picks the third choice in each
        THEN both answers are stored identically
        """
        stored = {}
        for style in ('stars', 'scale_strip'):
            survey, _section, question = self._survey(display_style=style)
            self._get(survey)
            self.client.post(f'/surveys/{survey.uuid}/s1/', {'q_rate': '3'})
            answer = Answer.objects.get(question=question)
            stored[style] = (answer.selected_choices, answer.numeric)

        self.assertEqual(stored['stars'], stored['scale_strip'])

    def test_switching_an_answered_question_to_stars_keeps_its_answers(self):
        """
        GIVEN a rating question with answers collected as a compact strip
        WHEN the creator switches it to stars
        THEN the stored answers are unchanged and still export
        """
        survey, _section, question = self._survey(display_style='scale_strip')
        self._get(survey)
        self.client.post(f'/surveys/{survey.uuid}/s1/', {'q_rate': '4'})
        before = Answer.objects.get(question=question)

        question.display_style = 'stars'
        question.save()

        after = Answer.objects.get(pk=before.pk)
        self.assertEqual(after.selected_choices, before.selected_choices)

        self.client.login(username='staruser', password='pass')
        response = self.client.get(f'/surveys/{survey.uuid}/download')
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            csv_text = zf.read(csv_name).decode('utf-8')
        self.assertIn('good', csv_text)

    def test_star_defaults_resolve_on_the_model(self):
        """
        GIVEN questions with and without an explicit colour
        WHEN the star colour is resolved
        THEN the model default #000000 reads as "unset" and yields gold
        """
        _survey, _section, question = self._survey()
        self.assertEqual(question.star_color(), '#f5b301')
        self.assertEqual(question.star_icon(), 'fas fa-star')

        question.color = '#112233'
        question.icon_class = 'far fa-circle'
        self.assertEqual(question.star_color(), '#112233')
        self.assertEqual(question.star_icon(), 'far fa-circle')

    def test_live_preview_renders_stars_for_an_unsaved_draft(self):
        """
        GIVEN the question dialog's live preview
        WHEN a rating draft is posted with the star style, a colour and an icon
        THEN the preview renders those icons in that colour, unsaved
        """
        survey, section, _q = self._survey()
        before = Question.objects.count()
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/question-preview/',
            {
                'input_type': 'rating',
                'name': 'How was it?',
                'display_style': 'stars',
                'color': '#22aa55',
                'icon_class': 'fas fa-leaf',
                'choices_json': '[{"code": 1, "name": "bad"}, {"code": 2, "name": "good"}]',
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('--star-color: #22aa55', html)
        self.assertEqual(html.count('fas fa-leaf'), 2)
        self.assertEqual(Question.objects.count(), before)


class StarRatingDefaultCountTest(TestCase):
    """Picking stars means five stars, without writing a choice list."""

    def setUp(self):
        self.org = _make_org('StarCountOrg')
        self.user = User.objects.create_user('starcount', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='star_count_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )

    def test_stars_without_choices_render_five_numbered_steps(self):
        """
        GIVEN a rating question set to stars whose choices were never defined
        WHEN a respondent opens the section
        THEN five stars render, numbered 1 to 5

        The style is picked far more often than a choice list is written; an
        empty question here would be the creator's first impression of it.
        """
        Question.objects.create(
            survey_section=self.section, name='How was it?', code='q_s',
            input_type='rating', order_number=1, display_style='stars', choices=None,
        )

        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()

        self.assertEqual(content.count('rating-stars__star'), 5)
        for step in ('1', '2', '3', '4', '5'):
            self.assertIn(f'value="{step}"', content)

    def test_the_fallback_is_not_written_to_the_question(self):
        """
        GIVEN a stars question rendered with the default five steps
        WHEN the question is re-read from the database
        THEN its choices are still unset — the default is resolved, not saved
        """
        question = Question.objects.create(
            survey_section=self.section, name='How was it?', code='q_s2',
            input_type='rating', order_number=1, display_style='stars', choices=None,
        )

        self.client.get(f'/surveys/{self.survey.uuid}/s1/')

        question.refresh_from_db()
        self.assertIsNone(question.choices)
        self.assertEqual(len(question.star_choices()), 5)

    def test_defined_choices_win_over_the_default(self):
        """
        GIVEN a stars question whose creator defined three named steps
        WHEN it renders
        THEN three stars render and the names are kept
        """
        Question.objects.create(
            survey_section=self.section, name='How was it?', code='q_s3',
            input_type='rating', order_number=1, display_style='stars',
            choices=[{"code": 1, "name": "meh"}, {"code": 2, "name": "fine"},
                     {"code": 3, "name": "great"}],
        )

        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()

        self.assertEqual(content.count('rating-stars__star'), 3)
        self.assertIn('great', content)

    def test_a_star_answer_exports_as_its_number(self):
        """
        GIVEN a stars question using the default numbered steps
        WHEN a respondent picks the fourth star and the creator exports
        THEN the answer reads as 4, not as a blank cell
        """
        Question.objects.create(
            survey_section=self.section, name='How was it?', code='q_s4',
            input_type='rating', order_number=1, display_style='stars',
            choices=[{"code": i, "name": str(i)} for i in range(1, 6)],
        )
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q_s4': '4'})

        self.client.login(username='starcount', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            csv_text = zf.read(csv_name).decode('utf-8')

        self.assertIn('How was it?', csv_text)
        self.assertIn('4', csv_text.split('\n')[1])

    def test_live_preview_shows_five_stars_for_a_fresh_draft(self):
        """
        GIVEN the question dialog with stars just picked and no choices typed
        WHEN the live preview renders the draft
        THEN it already shows five stars
        """
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/question-preview/',
            {'input_type': 'rating', 'name': 'How was it?', 'display_style': 'stars',
             'choices_json': ''},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode().count('rating-stars__star'), 5)


class StarColorEditorParityTest(SimpleTestCase):
    """The editor's gold swatch and the model's gold must be the same gold."""

    def test_modal_uses_the_models_default_star_colour(self):
        """
        GIVEN the question dialog, which pre-fills the colour picker with gold
              when a creator picks the star style
        WHEN that literal is compared with survey.models.DEFAULT_STAR_COLOR
        THEN they agree

        The dialog cannot read the constant (it is JavaScript in a template
        rendered from five different views), so this test is the link.
        """
        from pathlib import Path
        from survey.models import DEFAULT_STAR_COLOR

        modal = Path('survey/templates/editor/partials/question_form_modal.html').read_text()

        self.assertIn(f"colorInput.value = '{DEFAULT_STAR_COLOR}';", modal)


class StarRatingOpenKeepsChoicesTest(SimpleTestCase):
    """Opening a stars question must not seed five more stars (#452)."""

    def test_default_stars_wait_for_the_saved_choices(self):
        """
        GIVEN the question dialog, whose init block runs the stars toggle before
              the saved choices are loaded at the end of the script
        WHEN its source is read
        THEN the default five are seeded only when no saved choices exist or
             after they are loaded, and loading them re-runs the toggle

        The dialog's script is not executed by the suite; this pins the order
        that doubled a star rating's options on every open.
        """
        from pathlib import Path

        modal = Path('survey/templates/editor/partials/question_form_modal.html').read_text()

        self.assertIn("} else if (savedChoicesLoaded || !document.getElementById('existing-choices-data')) {", modal)
        load = modal.index('existingChoices.forEach(function(choice) {')
        tail = modal[load:]
        self.assertLess(tail.index('savedChoicesLoaded = true;'), tail.index('{% endif %}'))
        self.assertLess(tail.index('toggleStarCountField();'), tail.index('{% endif %}'))


class StarsDisplayStyleImportTest(TestCase):
    """`stars` survives a ZIP round trip (change copenhagen-demo)."""

    def test_stars_round_trip(self):
        """
        GIVEN a survey with a stars rating question and a stars survey default
        WHEN it is exported and imported again
        THEN both keep `stars`
        """
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        org = Organization.objects.create(name="Stars Org")
        survey = SurveyHeader.objects.create(name="stars_survey", organization=org, redirect_url="#",
                                             style_settings={'rating_display_style': 'stars'})
        section = SurveySection.objects.create(survey_header=survey, name="s1", code="S1", is_head=True)
        Question.objects.create(survey_section=section, code="STARQ1", name="Rate", input_type="rating",
                                choices=[{"code": i, "name": str(i)} for i in range(1, 6)],
                                display_style="stars")
        buf = BytesIO()
        export_survey_to_zip(survey, buf)
        buf.seek(0)
        survey.name = "stars_survey_old"
        survey.save()
        imported, _ = import_survey_from_zip(buf, organization=org)
        q = Question.objects.get(survey_section__survey_header=imported, input_type='rating')
        self.assertEqual(q.display_style, 'stars')
        self.assertEqual(imported.style_settings.get('rating_display_style'), 'stars')
