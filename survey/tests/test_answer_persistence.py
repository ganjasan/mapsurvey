"""Tests for the `answer-persistence` capability (openspec/specs/answer-persistence/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from io import BytesIO
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.tests.helpers import _make_org


class AnswerBranchByInputTypeTest(TestCase):
    """Answer storage dispatches on input_type, never on stale `choices`.

    A point question that kept a choices list from a type switch used to route
    its GeoJSON into int() — a 500 on every submit (prod incident 2026-08-24,
    question Q_7633107523).
    """

    STALE_CHOICES = [{"code": 1, "name": "Trespassing"}, {"code": 2, "name": "Dumping"}]

    def setUp(self):
        self.org = _make_org('BranchOrg')
        self.user = User.objects.create_user(username='branchuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='branch_survey', organization=self.org,
            redirect_url='/thanks/', status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section One',
            code='BR1', is_head=True,
        )
        self.point_q = Question.objects.create(
            survey_section=self.section, name='Where?', input_type='point',
            order_number=1, choices=self.STALE_CHOICES,
        )
        self.text_sub = Question.objects.create(
            survey_section=self.section, name='Details', input_type='text',
            order_number=1, parent_question_id=self.point_q,
            choices=self.STALE_CHOICES,
        )
        self.dt_sub = Question.objects.create(
            survey_section=self.section, name='When?', input_type='datetime',
            order_number=2, parent_question_id=self.point_q,
        )
        self.dt_q = Question.objects.create(
            survey_section=self.section, name='Top when?', input_type='datetime',
            order_number=3,
        )

    def _feature(self, props=None):
        properties = {'question_id': self.point_q.code}
        properties.update(props or {})
        return json.dumps({
            'type': 'Feature',
            'properties': properties,
            'geometry': {'type': 'Point', 'coordinates': [-119.4, 49.9]},
        })

    def _session_id(self):
        return self.client.session['survey_session_id']

    def test_point_with_stale_choices_saves_geometry(self):
        """
        GIVEN a point question whose choices holds a stale non-empty list
        WHEN a respondent submits the section with a drawn point
        THEN the geometry is saved and the submit succeeds (was ValueError/500)
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        response = self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {self.point_q.code: self._feature() + '|'},
        )
        self.assertEqual(response.status_code, 302)
        answer = Answer.objects.get(question=self.point_q, survey_session_id=self._session_id())
        self.assertIsNotNone(answer.point)

    def test_text_subquestion_with_stale_choices_saves_text(self):
        """
        GIVEN a text sub-question of a geo question with stale choices
        WHEN the feature properties carry a text value
        THEN it is stored in `text`, not parsed as a choice code
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        feature = self._feature({self.text_sub.code: ['broken window']})
        self.client.post(f'/surveys/{self.survey.uuid}/sec1/', {self.point_q.code: feature + '|'})
        sub = Answer.objects.get(question=self.text_sub, survey_session_id=self._session_id())
        self.assertEqual(sub.text, 'broken window')
        self.assertIsNone(sub.selected_choices)

    def test_datetime_subquestion_value_persists(self):
        """
        GIVEN a datetime sub-question of a geo question
        WHEN the feature properties carry a datetime value
        THEN the sub-answer stores it in `text` (it used to save an empty row)
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        feature = self._feature({self.dt_sub.code: ['2026-08-24T21:15']})
        self.client.post(f'/surveys/{self.survey.uuid}/sec1/', {self.point_q.code: feature + '|'})
        sub = Answer.objects.get(question=self.dt_sub, survey_session_id=self._session_id())
        self.assertEqual(sub.text, '2026-08-24T21:15')

    def test_top_level_datetime_round_trips(self):
        """
        GIVEN a top-level datetime question
        WHEN a respondent submits a value and revisits the section
        THEN the value is stored in `text` and prepopulates the field
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {self.dt_q.code: '2026-08-24T21:15'},
        )
        answer = Answer.objects.get(question=self.dt_q, survey_session_id=self._session_id())
        self.assertEqual(answer.text, '2026-08-24T21:15')
        revisit = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertContains(revisit, '2026-08-24T21:15')

    def test_choice_questions_unaffected(self):
        """
        GIVEN choice and number questions
        WHEN a respondent submits them
        THEN storage matches the pre-change behavior
        """
        choice_q = Question.objects.create(
            survey_section=self.section, name='Pick', input_type='choice',
            choices=self.STALE_CHOICES, order_number=4,
        )
        number_q = Question.objects.create(
            survey_section=self.section, name='How many', input_type='number',
            order_number=5,
        )
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {choice_q.code: '2', number_q.code: '7'},
        )
        sid = self._session_id()
        self.assertEqual(Answer.objects.get(question=choice_q, survey_session_id=sid).selected_choices, [2])
        self.assertEqual(Answer.objects.get(question=number_q, survey_session_id=sid).numeric, 7.0)


class ChoicesClearedOnNonChoiceTypesTest(TestCase):
    """Every write path forces choices=None for types that do not use them."""

    STALE_JSON = '[{"code": 1, "name": "Old option"}]'

    def setUp(self):
        self.org = _make_org('ClearOrg')
        self.user = User.objects.create_user(username='clearuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='clear_survey', organization=self.org, status='draft',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='S', code='CL1', is_head=True,
        )
        self.client.login(username='clearuser', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_edit_type_switch_to_point_clears_choices(self):
        """
        GIVEN a choice question with options
        WHEN the creator switches its type to point while the form still posts
             the old choices_json
        THEN the saved question has choices=None
        """
        q = Question.objects.create(
            survey_section=self.section, name='Pick', input_type='choice',
            choices=[{"code": 1, "name": "Old option"}], order_number=1,
        )
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/edit/',
            {'name': 'Pick', 'input_type': 'point', 'color': '#000000',
             'choices_json': self.STALE_JSON},
        )
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.input_type, 'point')
        self.assertIsNone(q.choices)

    def test_create_geo_question_ignores_posted_choices(self):
        """
        GIVEN the question create form
        WHEN a point question is created with choices_json posted
        THEN the created question has choices=None
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Spot', 'input_type': 'point', 'color': '#000000',
             'choices_json': self.STALE_JSON},
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Spot')
        self.assertIsNone(q.choices)

    def test_create_subquestion_ignores_posted_choices(self):
        """
        GIVEN a geo parent question
        WHEN a text sub-question is created with choices_json posted
        THEN the created sub-question has choices=None
        """
        parent = Question.objects.create(
            survey_section=self.section, name='Where', input_type='point', order_number=1,
        )
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{parent.id}/subquestions/new/',
            {'name': 'Detail', 'input_type': 'text', 'color': '#000000',
             'choices_json': self.STALE_JSON},
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Detail')
        self.assertIsNone(q.choices)

    def test_import_normalizes_choices_on_point_question(self):
        """
        GIVEN an exported survey whose point question carries a choices list
        WHEN the ZIP is imported
        THEN the created question has choices=None
        """
        Question.objects.create(
            survey_section=self.section, code='CLPT01', name='Spot',
            input_type='point', order_number=1,
        )
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
        survey_json["survey"]["name"] = "clear_imported"
        for sec in survey_json["survey"]["sections"]:
            for qd in sec["questions"]:
                qd["choices"] = [{"code": 1, "name": "Poison"}]
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        buf.seek(0)

        imported, _ = import_survey_from_zip(buf)

        q = Question.objects.get(survey_section__survey_header=imported, name='Spot')
        self.assertIsNone(q.choices)

    def test_migration_clears_only_nonchoice_types(self):
        """
        GIVEN poisoned geo/text questions and a legitimate choice question
        WHEN the 0060 data migration function runs
        THEN only the non-choice types lose their choices
        """
        from importlib import import_module
        mig = import_module('survey.migrations.0060_clear_choices_on_nonchoice_types')

        poisoned_geo = Question.objects.create(
            survey_section=self.section, name='Geo', input_type='point',
            choices=[{"code": 1, "name": "Stale"}], order_number=1,
        )
        poisoned_text = Question.objects.create(
            survey_section=self.section, name='Free', input_type='text',
            choices=[{"code": 1, "name": "Stale"}], order_number=2,
        )
        legit_choice = Question.objects.create(
            survey_section=self.section, name='Pick', input_type='choice',
            choices=[{"code": 1, "name": "Keep"}], order_number=3,
        )
        legit_ranking = Question.objects.create(
            survey_section=self.section, name='Order', input_type='ranking',
            choices=[{"code": 1, "name": "Keep"}], order_number=4,
        )

        from django.apps import apps as django_apps
        mig.clear_stale_choices(django_apps, None)

        poisoned_geo.refresh_from_db()
        poisoned_text.refresh_from_db()
        legit_choice.refresh_from_db()
        legit_ranking.refresh_from_db()
        self.assertIsNone(poisoned_geo.choices)
        self.assertIsNone(poisoned_text.choices)
        self.assertEqual(legit_choice.choices, [{"code": 1, "name": "Keep"}])
        self.assertEqual(legit_ranking.choices, [{"code": 1, "name": "Keep"}])


class MalformedGeometryChunkTest(TestCase):
    """Spec answer-persistence: a geometry chunk that does not parse skips
    itself, never the section (change fix-geo-post-bad-json)."""

    VALID = ('{"type":"Feature","properties":{"question_id":"PT"},'
             '"geometry":{"type":"Point","coordinates":[13.3423,52.5013]}}')

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Chunk Org")
        self.survey = SurveyHeader.objects.create(
            name="chunks", organization=self.org, status='published',
            available_languages=[], redirect_url="#",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="place", title="Place", code="S1",
            is_head=True,
        )
        self.point = Question.objects.create(
            survey_section=self.section, code="PT", order_number=1, name="Where?",
            input_type="point",
        )
        self.note = Question.objects.create(
            survey_section=self.section, code="NOTE", order_number=2, name="Why?",
            input_type="text_line",
        )

    def _post(self, geo_value):
        self.client.get('/surveys/chunks/place/')
        return self.client.post('/surveys/chunks/place/', {'PT': geo_value, 'NOTE': 'benches'})

    def _answers(self, question):
        session = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        return Answer.objects.filter(survey_session=session, question=question)

    def test_comma_prefixed_chunk_is_skipped_and_the_rest_persists(self):
        """
        GIVEN a section with a point question and a text question
        WHEN the POST carries ",{feature}|" under the point code (htmx array join)
        THEN the response is the normal redirect, the unreadable chunk stores
             nothing, and the text answer is stored

        Reproduces the 2026-09-07 incident: one iPhone respondent, 42 x 500 on
        the same section until a page reload.
        """
        with self.assertLogs('survey.views', level='WARNING') as logs:
            response = self._post(',' + self.VALID + '|')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._answers(self.point).count(), 0)
        self.assertEqual(self._answers(self.note).get().text, 'benches')
        self.assertIn('PT', logs.output[0])

    def test_valid_chunk_after_a_malformed_one_is_kept(self):
        """
        GIVEN the same section
        WHEN the posted value is "garbage|{feature}|"
        THEN exactly one point answer is stored, from the valid chunk
        """
        response = self._post('garbage|' + self.VALID + '|')
        self.assertEqual(response.status_code, 302)
        stored = self._answers(self.point)
        self.assertEqual(stored.count(), 1)
        self.assertAlmostEqual(stored.get().point.x, 13.3423, places=4)

    def test_json_that_is_not_a_feature_is_skipped(self):
        """
        GIVEN the same section
        WHEN a chunk is "[]" or "{}" (valid JSON, no geometry)
        THEN it stores nothing and the submission succeeds
        """
        for chunk in ('[]', '{}'):
            with self.subTest(chunk=chunk):
                response = self._post(chunk + '|')
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self._answers(self.point).count(), 0)
