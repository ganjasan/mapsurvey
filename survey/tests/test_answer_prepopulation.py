"""Tests for the `answer-prepopulation` capability (openspec/specs/answer-prepopulation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.gis.geos import Point
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer


class AnswerPrepopulationTest(TestCase):
    """Tests for answer prepopulation when revisiting survey sections."""

    def setUp(self):
        """Set up a survey with multiple question types across two sections."""
        self.client = Client()
        self.org = Organization.objects.create(name="Prepop Test Org")
        self.survey = SurveyHeader.objects.create(
            name="prepop_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Section One",
            code="S1",
            is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey,
            name="section2",
            title="Section Two",
            code="S2",
        )
        self.section1.next_section = self.section2
        self.section1.save()
        self.section2.prev_section = self.section1
        self.section2.save()

        self.text_q = Question.objects.create(
            survey_section=self.section1,
            name="Your name",
            input_type="text",
            order_number=1,
        )
        self.number_q = Question.objects.create(
            survey_section=self.section1,
            name="Your age",
            input_type="number",
            order_number=2,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section1,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            order_number=3,
        )
        self.multichoice_q = Question.objects.create(
            survey_section=self.section1,
            name="Colors",
            input_type="multichoice",
            choices=[
                {"code": 1, "name": "Red"},
                {"code": 2, "name": "Blue"},
                {"code": 3, "name": "Green"},
            ],
            order_number=4,
        )
        self.point_q = Question.objects.create(
            survey_section=self.section1,
            name="Location",
            input_type="point",
            order_number=5,
        )
        # A question in section2 to verify isolation
        self.section2_q = Question.objects.create(
            survey_section=self.section2,
            name="Feedback",
            input_type="text",
            order_number=1,
        )

    def _visit_section(self, section_name):
        """GET a section and return the response."""
        return self.client.get(f'/surveys/prepop_survey/{section_name}/')

    def _submit_section(self, section_name, data):
        """POST to a section with given data."""
        return self.client.post(f'/surveys/prepop_survey/{section_name}/', data)

    def test_scalar_field_prepopulation(self):
        """
        GIVEN a section with text, number, and choice answers saved
        WHEN the user revisits the section via GET
        THEN the form initial values contain the previously saved answers
        """
        # First visit to create session
        self._visit_section('section1')

        # Submit answers
        self._submit_section('section1', {
            self.text_q.code: 'Alice',
            self.number_q.code: '25',
            self.choice_q.code: '1',
            self.multichoice_q.code: ['1', '3'],
        })

        # Revisit section1 — verify rendered HTML contains saved values
        response = self._visit_section('section1')

        self.assertContains(response, 'Alice')
        self.assertContains(response, '25')
        # Choice radio button should be checked
        self.assertContains(response, 'checked')

    def test_geo_answer_restoration(self):
        """
        GIVEN a section with a point geo answer saved
        WHEN the user revisits the section via GET
        THEN existing_geo_answers context contains correct GeoJSON
        """
        # Create session and save a point answer directly
        self._visit_section('section1')
        session_id = self.client.session['survey_session_id']
        session = SurveySession.objects.get(pk=session_id)
        Answer.objects.create(
            survey_session=session,
            question=self.point_q,
            point=Point(30.5, 60.0, srid=4326),
        )

        # Revisit section1
        response = self._visit_section('section1')
        geo_data = response.context['existing_geo_answers']

        self.assertIn(self.point_q.code, geo_data)
        features = geo_data[self.point_q.code]
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]['geometry']['type'], 'Point')
        self.assertEqual(features[0]['properties']['question_id'], self.point_q.code)

    def test_resubmission_replaces_answers(self):
        """
        GIVEN a section submitted with answers
        WHEN the user re-submits with different values
        THEN only the latest answers exist in the database
        """
        # First visit to create session
        self._visit_section('section1')
        session_id = self.client.session['survey_session_id']

        # First submission
        self._submit_section('section1', {
            self.text_q.code: 'Alice',
            self.number_q.code: '25',
        })
        self.assertEqual(
            Answer.objects.filter(survey_session_id=session_id, question=self.text_q).count(),
            1,
        )

        # Second submission with different values
        self._submit_section('section1', {
            self.text_q.code: 'Bob',
            self.number_q.code: '30',
        })

        # Only latest answers should exist
        text_answers = Answer.objects.filter(survey_session_id=session_id, question=self.text_q)
        self.assertEqual(text_answers.count(), 1)
        self.assertEqual(text_answers.first().text, 'Bob')

        number_answers = Answer.objects.filter(survey_session_id=session_id, question=self.number_q)
        self.assertEqual(number_answers.count(), 1)
        self.assertEqual(number_answers.first().numeric, 30.0)

    def test_first_visit_shows_empty_form(self):
        """
        GIVEN a section with no saved answers
        WHEN the user visits it for the first time
        THEN no geo answers are present in the context
        """
        response = self._visit_section('section1')
        geo_data = response.context['existing_geo_answers']

        self.assertEqual(geo_data, {})

    def test_resubmission_does_not_affect_other_sections(self):
        """
        GIVEN answers saved in section2
        WHEN section1 is re-submitted
        THEN section2 answers remain unchanged
        """
        # Visit section1 to create session
        self._visit_section('section1')
        session_id = self.client.session['survey_session_id']
        session = SurveySession.objects.get(pk=session_id)

        # Save an answer in section2 directly
        Answer.objects.create(
            survey_session=session,
            question=self.section2_q,
            text="Great survey",
        )

        # Submit section1
        self._submit_section('section1', {
            self.text_q.code: 'Alice',
        })

        # Section2 answer should still exist
        self.assertTrue(
            Answer.objects.filter(survey_session=session, question=self.section2_q).exists()
        )
