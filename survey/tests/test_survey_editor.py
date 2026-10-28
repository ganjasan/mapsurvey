"""Tests for the `survey-editor` capability (openspec/specs/survey-editor/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
import json
import re
import uuid
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.models import SurveySectionTranslation, QuestionTranslation
from survey.analytics import SurveyAnalyticsService
from survey.cloning import clone_question, clone_section
from django.conf import settings
import os
from survey.tests.helpers import _make_org, _make_survey_with_section, _objects_layer


class EditorAuthTest(TestCase):
    """Tests that all editor views require authentication."""

    def test_unauthenticated_redirects_to_login(self):
        """
        GIVEN an unauthenticated user
        WHEN they access any editor URL
        THEN they are redirected to the login page
        """
        import uuid
        fake_uuid = uuid.uuid4()
        urls = [
            '/editor/surveys/new/',
            f'/editor/surveys/{fake_uuid}/',
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"{url} should redirect")
            self.assertIn('login', response.url, f"{url} should redirect to login")


class EditorSurveyCreateTest(TestCase):
    """Tests for survey creation via the editor."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')

    def test_create_survey_happy_path(self):
        """
        GIVEN an authenticated user
        WHEN they submit the survey creation form with a valid name
        THEN a SurveyHeader is created with a default section
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'my_new_survey',
            'redirect_url': '#',
            'visibility': 'private',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='my_new_survey')
        self.assertIsNotNone(survey)
        sections = SurveySection.objects.filter(survey_header=survey)
        self.assertEqual(sections.count(), 1)
        self.assertTrue(sections.first().is_head)

    def test_create_survey_duplicate_name_allowed(self):
        """
        GIVEN an existing survey with name 'dup_survey'
        WHEN a user tries to create another survey with the same name
        THEN the survey is created (duplicate names are allowed)
        """
        SurveyHeader.objects.create(name='dup_survey', organization=self.org)
        response = self.client.post('/editor/surveys/new/', {
            'name': 'dup_survey',
            'redirect_url': '#',
            'visibility': 'private',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SurveyHeader.objects.filter(name='dup_survey').count(), 2)

    def test_create_survey_get_renders_form(self):
        """
        GIVEN an authenticated user
        WHEN they GET the creation page
        THEN the form is rendered
        """
        response = self.client.get('/editor/surveys/new/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create New Survey')

    def test_create_survey_minimal_form_gets_model_defaults(self):
        """
        GIVEN an authenticated user
        WHEN they submit the creation form with only a name
        THEN the survey is created with model defaults for every deferred
             setting (visibility, redirect, basemaps, thanks, languages)
        """
        response = self.client.post('/editor/surveys/new/', {'name': 'minimal_survey'})
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='minimal_survey')
        self.assertEqual(survey.visibility, 'private')
        self.assertEqual(survey.redirect_url, '#')
        self.assertEqual(survey.basemaps, ['streets', 'satellite', 'topo'])
        self.assertEqual(survey.thanks_html, {})
        self.assertEqual(survey.available_languages, [])
        self.assertFalse(survey.cover_image)

    def test_create_survey_saves_map_position(self):
        """
        GIVEN an authenticated user
        WHEN they submit the creation form with a name and map fields
        THEN the survey stores the start position, zoom, and geolocation flag
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'placed_survey',
            'map_lat': '42.8746', 'map_lng': '74.5698', 'map_zoom': '13',
            'use_geolocation': '1',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='placed_survey')
        self.assertAlmostEqual(survey.start_map_postion.y, 42.8746, places=4)
        self.assertAlmostEqual(survey.start_map_postion.x, 74.5698, places=4)
        self.assertEqual(survey.start_map_zoom, 13)
        self.assertTrue(survey.use_geolocation)

    def test_create_page_defers_settings_to_settings_panel(self):
        """
        GIVEN an authenticated user
        WHEN they GET the creation page
        THEN the truly deferred fields (thanks html, visibility, cover) are
             absent and the page points to Survey settings, while the
             foundational fields (languages, default base map) are present
        """
        response = self.client.get('/editor/surveys/new/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id_thanks_html')
        self.assertNotContains(response, 'id_visibility')
        self.assertNotContains(response, 'id_cover_image')
        self.assertContains(response, 'Survey settings')
        self.assertContains(response, 'id_available_languages')
        self.assertContains(response, 'name="default_basemap"')

    def test_create_survey_saves_languages(self):
        """
        GIVEN an authenticated user
        WHEN they submit the creation form with chosen languages
        THEN the survey stores exactly those available_languages
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'multilang_survey',
            'available_languages': '["en", "ru"]',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='multilang_survey')
        self.assertEqual(survey.available_languages, ['en', 'ru'])

    def test_create_survey_saves_default_basemap(self):
        """
        GIVEN an authenticated user
        WHEN they pick a base map on the creation form
        THEN the survey stores it as default_basemap and keeps all basemaps
             available (model default)
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'sat_survey', 'default_basemap': 'satellite',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='sat_survey')
        self.assertEqual(survey.default_basemap, 'satellite')
        self.assertEqual(survey.basemaps, ['streets', 'satellite', 'topo'])

    def test_create_survey_ignores_invalid_basemap(self):
        """
        GIVEN an authenticated user
        WHEN they post an unknown default_basemap value
        THEN it is ignored (not persisted)
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'bad_basemap_survey', 'default_basemap': 'bogus',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='bad_basemap_survey')
        self.assertNotEqual(survey.default_basemap, 'bogus')


class EditorSectionCRUDTest(TestCase):
    """Tests for section CRUD in the editor."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='test_editor', visibility='private', organization=self.org)
        self.section_a = SurveySection.objects.create(
            survey_header=self.survey, name='a', title='Section A', code='SA', is_head=True,
        )
        self.section_b = SurveySection.objects.create(
            survey_header=self.survey, name='b', title='Section B', code='SB',
        )
        self.section_a.next_section = self.section_b
        self.section_a.save(update_fields=['next_section'])
        self.section_b.prev_section = self.section_a
        self.section_b.save(update_fields=['prev_section'])

    def test_create_section_appends_to_linked_list(self):
        """
        GIVEN a survey with sections [A, B]
        WHEN a new section is created
        THEN it is appended after B in the linked list
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/new/',
            HTTP_X_CSRFTOKEN='test',
        )
        self.assertEqual(response.status_code, 200)
        new_section = SurveySection.objects.filter(survey_header=self.survey).exclude(
            id__in=[self.section_a.id, self.section_b.id]
        ).first()
        self.assertIsNotNone(new_section)
        self.section_b.refresh_from_db()
        self.assertEqual(self.section_b.next_section_id, new_section.id)
        self.assertEqual(new_section.prev_section_id, self.section_b.id)

    def test_delete_section_relinks_neighbors(self):
        """
        GIVEN sections [A → B]
        WHEN B is deleted
        THEN A.next_section becomes None
        """
        self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.section_b.id}/delete/')
        self.section_a.refresh_from_db()
        self.assertIsNone(self.section_a.next_section_id)
        self.assertFalse(SurveySection.objects.filter(id=self.section_b.id).exists())

    def test_edit_section_title(self):
        """
        GIVEN a section with title 'Section A'
        WHEN the user updates the title to 'Introduction'
        THEN the section title is updated
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section_a.id}/',
            {'title': 'Introduction', 'subheading': '', 'code': 'SA'},
        )
        self.section_a.refresh_from_db()
        self.assertEqual(self.section_a.title, 'Introduction')


class EditorSectionReorderTest(TestCase):
    """Tests for section drag-and-drop reordering."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='reorder_test', visibility='private', organization=self.org)
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name='s2', title='S2', code='S2',
        )
        self.s3 = SurveySection.objects.create(
            survey_header=self.survey, name='s3', title='S3', code='S3',
        )
        # Link: s1 → s2 → s3
        self.s1.next_section = self.s2
        self.s1.save(update_fields=['next_section'])
        self.s2.prev_section = self.s1
        self.s2.next_section = self.s3
        self.s2.save(update_fields=['prev_section', 'next_section'])
        self.s3.prev_section = self.s2
        self.s3.save(update_fields=['prev_section'])

    def test_reorder_rebuilds_linked_list(self):
        """
        GIVEN sections [S1, S2, S3]
        WHEN reordered to [S3, S1, S2]
        THEN linked list is rebuilt: S3(head) → S1 → S2
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/reorder/',
            data=json.dumps({'section_ids': [self.s3.id, self.s1.id, self.s2.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)

        self.s1.refresh_from_db()
        self.s2.refresh_from_db()
        self.s3.refresh_from_db()

        self.assertTrue(self.s3.is_head)
        self.assertFalse(self.s1.is_head)
        self.assertFalse(self.s2.is_head)

        self.assertEqual(self.s3.next_section_id, self.s1.id)
        self.assertIsNone(self.s3.prev_section_id)
        self.assertEqual(self.s1.prev_section_id, self.s3.id)
        self.assertEqual(self.s1.next_section_id, self.s2.id)
        self.assertEqual(self.s2.prev_section_id, self.s1.id)
        self.assertIsNone(self.s2.next_section_id)


class EditorQuestionCRUDTest(TestCase):
    """Tests for question CRUD in the editor."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='q_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )

    def test_create_text_question(self):
        """
        GIVEN a section with no questions
        WHEN a text question is created
        THEN the question appears in the section with correct attributes
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Your feedback', 'input_type': 'text', 'color': '#000000'},
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Your feedback')
        self.assertEqual(q.input_type, 'text')
        self.assertEqual(q.order_number, 1)

    def test_create_choice_question_with_choices(self):
        """
        GIVEN a section
        WHEN a choice question is created with choices JSON
        THEN the question has correct choices
        """
        choices = [{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {
                'name': 'Do you agree?',
                'input_type': 'choice',
                'color': '#000000',
                'choices_json': json.dumps(choices),
            },
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Do you agree?')
        self.assertEqual(q.choices, choices)

    def test_delete_question(self):
        """
        GIVEN a section with one question
        WHEN the question is deleted
        THEN it no longer exists
        """
        q = Question.objects.create(
            survey_section=self.section, name='Delete me', input_type='text',
        )
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/delete/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(id=q.id).exists())

    def test_edit_question(self):
        """
        GIVEN a text question
        WHEN it is edited to change the name
        THEN the name is updated
        """
        q = Question.objects.create(
            survey_section=self.section, name='Old name', input_type='text',
        )
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/edit/',
            {'name': 'New name', 'input_type': 'text', 'color': '#000000'},
        )
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.name, 'New name')


class EditorQuestionReorderTest(TestCase):
    """Tests for question reordering."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='qr_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q1 = Question.objects.create(
            survey_section=self.section, name='Q1', input_type='text', order_number=0,
        )
        self.q2 = Question.objects.create(
            survey_section=self.section, name='Q2', input_type='text', order_number=1,
        )
        self.q3 = Question.objects.create(
            survey_section=self.section, name='Q3', input_type='text', order_number=2,
        )

    def test_reorder_updates_order_number(self):
        """
        GIVEN questions [Q1(0), Q2(1), Q3(2)]
        WHEN reordered to [Q3, Q1, Q2]
        THEN order_numbers become Q3(0), Q1(1), Q2(2)
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/reorder/',
            data=json.dumps({'question_ids': [self.q3.id, self.q1.id, self.q2.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        self.q1.refresh_from_db()
        self.q2.refresh_from_db()
        self.q3.refresh_from_db()
        self.assertEqual(self.q3.order_number, 0)
        self.assertEqual(self.q1.order_number, 1)
        self.assertEqual(self.q2.order_number, 2)


class EditorSubquestionTest(TestCase):
    """Tests for sub-question creation."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='sub_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.geo_question = Question.objects.create(
            survey_section=self.section, name='Mark location', input_type='point',
        )

    def test_create_subquestion(self):
        """
        GIVEN a geo question
        WHEN a sub-question is created for it
        THEN the sub-question has parent_question_id set correctly
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/subquestions/new/',
            {'name': 'Rate this place', 'input_type': 'choice', 'color': '#000000',
             'choices_json': json.dumps([{"code": 1, "name": "Good"}, {"code": 2, "name": "Bad"}])},
        )
        self.assertEqual(response.status_code, 200)
        sub = Question.objects.get(name='Rate this place')
        self.assertEqual(sub.parent_question_id_id, self.geo_question.id)

    def test_add_subquestion_button_visible_on_geo_question(self):
        """
        GIVEN a draft survey with a geo (point) question
        WHEN the editor section detail is fetched
        THEN the response renders an "Add Sub-question" button wired to editor_subquestion_create for that question
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Sub-question')
        self.assertContains(
            response,
            f'/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/subquestions/new/',
        )
        self.assertContains(response, 'add-question-btn--sub')

    def test_add_subquestion_button_absent_on_non_geo_question(self):
        """
        GIVEN a draft survey with a non-geo (text) question alongside a geo question
        WHEN the editor section detail is fetched
        THEN no Add Sub-question entry point is rendered for the text question
        """
        text_question = Question.objects.create(
            survey_section=self.section, name='Comment', input_type='text',
        )
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            f'/editor/surveys/{self.survey.uuid}/questions/{text_question.id}/subquestions/new/',
        )

    @override_settings(LIVE_SURVEY_EDITING=False)
    def test_add_subquestion_button_disabled_in_readonly(self):
        """
        GIVEN a published survey with a geo question, live editing switched off
        WHEN the editor section detail is fetched
        THEN the Add Sub-question button is rendered disabled with the read-only tooltip
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add Sub-question')
        self.assertContains(response, 'Create a draft to edit')
        # In read-only state the button must NOT carry the hx-get URL — the disabled
        # branch of the template skips it entirely.
        self.assertNotContains(
            response,
            f'hx-get="/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/subquestions/new/"',
        )

    def test_legacy_sitemap_icon_removed(self):
        """
        GIVEN a draft survey with a geo question
        WHEN the editor section detail is fetched
        THEN the legacy fa-sitemap icon button is no longer present
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'fa-sitemap')

    def test_subquestion_create_form_excludes_geo_input_types(self):
        """
        GIVEN a geo question
        WHEN the new sub-question modal is opened
        THEN the input_type select offers no point/line/polygon options
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/subquestions/new/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="point"')
        self.assertNotContains(response, 'value="line"')
        self.assertNotContains(response, 'value="polygon"')
        self.assertContains(response, 'value="text"')
        self.assertContains(response, 'value="choice"')

    def test_subquestion_create_rejects_geo_input_types(self):
        """
        GIVEN a geo question
        WHEN a POST attempts to create a sub-question with input_type="point"
        THEN no Question is created and the form is re-rendered with errors
        """
        before = Question.objects.filter(parent_question_id=self.geo_question).count()
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/subquestions/new/',
            {'name': 'Nested point', 'input_type': 'point', 'color': '#000000'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Question.objects.filter(parent_question_id=self.geo_question).count(),
            before,
        )

    def test_subquestion_edit_form_excludes_geo_input_types(self):
        """
        GIVEN an existing sub-question (non-geo)
        WHEN its edit modal is opened
        THEN the input_type select offers no point/line/polygon options
        """
        sub = Question.objects.create(
            survey_section=self.section,
            parent_question_id=self.geo_question,
            name='Comment', input_type='text',
        )
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{sub.id}/edit/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="point"')
        self.assertNotContains(response, 'value="polygon"')

    def test_top_level_question_edit_form_keeps_geo_input_types(self):
        """
        GIVEN a top-level (non-sub) question
        WHEN its edit modal is opened
        THEN the input_type select still offers point/line/polygon options
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/edit/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="point"')
        self.assertContains(response, 'value="line"')
        self.assertContains(response, 'value="polygon"')


class DashboardCompletionCountsTest(TestCase):
    """Dashboard card numbers come from family-wide batched counts (#362, change
    dashboard-batched-kpis): same numbers as the Responses overview, a query count
    that does not grow with the survey list."""

    def setUp(self):
        self.org = _make_org('KpiOrg')
        self.user = User.objects.create_user(username='kpiowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='kpiowner', password='pass')

    def _header(self, name, **kwargs):
        """A survey version with two sections; returns (header, q_first, q_last)."""
        header = SurveyHeader.objects.create(
            name=name, organization=self.org, created_by=self.user, **kwargs,
        )
        last = SurveySection.objects.create(survey_header=header, name='last', code='S2')
        first = SurveySection.objects.create(
            survey_header=header, name='first', code='S1', is_head=True, next_section=last,
        )
        q_first = Question.objects.create(
            survey_section=first, name='Q1', code='q1', input_type='text', order_number=1,
        )
        q_last = Question.objects.create(
            survey_section=last, name='Q2', code='q2', input_type='text', order_number=1,
        )
        return header, q_first, q_last

    def _session(self, header, *questions, **kwargs):
        session = SurveySession.objects.create(survey=header, **kwargs)
        for q in questions:
            Answer.objects.create(survey_session=session, question=q, text='x')
        return session

    def _card(self, response, survey):
        return next(s for s in response.context['survey_headers'] if s.id == survey.id)

    def test_card_numbers_match_overview_across_versions(self):
        """
        GIVEN a survey with an archived version, completed and partial sessions on
              both, a deleted completed session, an empty session and a completed
              preview session on its draft copy
        WHEN the dashboard is loaded
        THEN the card's completed count and rate equal get_overview() — 3 of 6, 50%
        """
        from survey.analytics import SurveyAnalyticsService
        canonical, c_first, c_last = self._header('kpi_family', status='published', version_number=2)
        archived, a_first, a_last = self._header(
            'kpi_family', status='closed', is_canonical=False,
            canonical_survey=canonical, version_number=1,
        )
        draft, d_first, d_last = self._header('[draft] kpi_family', published_version=canonical)
        self._session(canonical, c_first, c_last)
        self._session(canonical, c_first)
        self._session(canonical)
        self._session(archived, a_first, a_last)
        self._session(archived, a_last)
        self._session(archived, a_first)
        self._session(canonical, c_first, c_last, is_deleted=True)
        self._session(draft, d_first, d_last)

        response = self.client.get('/editor/')

        overview = SurveyAnalyticsService(canonical).get_overview()
        card = self._card(response, canonical)
        self.assertEqual((overview['completed_count'], overview['completion_rate']), (3, 50))
        self.assertEqual(card.completed_count, overview['completed_count'])
        self.assertEqual(card.completion_rate, overview['completion_rate'])

    def test_survey_without_sessions_shows_zero(self):
        """
        GIVEN a survey with sections and no sessions, and one with no sections at all
        WHEN the dashboard is loaded
        THEN both cards show 0 completed and 0%
        """
        survey, _, _ = self._header('kpi_empty', status='published')
        bare = SurveyHeader.objects.create(name='kpi_bare', organization=self.org, created_by=self.user)

        response = self.client.get('/editor/')

        for s in (survey, bare):
            card = self._card(response, s)
            self.assertEqual((card.completed_count, card.completion_rate), (0, 0))

    def _populate(self, n):
        for i in range(n):
            canonical, c_first, c_last = self._header(f'kpi_{i}', status='published', version_number=2)
            archived, a_first, a_last = self._header(
                f'kpi_{i}', status='closed', is_canonical=False,
                canonical_survey=canonical, version_number=1,
            )
            self._session(canonical, c_first, c_last)
            self._session(archived, a_first)

    def _dashboard_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get('/editor/')
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_query_count_does_not_grow_with_surveys(self):
        """
        GIVEN a workspace with 2 versioned surveys, then the same with 8
        WHEN the dashboard is loaded each time
        THEN both loads run the same number of queries
        """
        self._populate(2)
        self.client.get('/editor/')  # warm per-process caches (changelog, sites)
        with_two = self._dashboard_queries()
        SurveyHeader.objects.filter(organization=self.org).update(name='kpi_old')
        self._populate(6)
        with_eight = self._dashboard_queries()
        self.assertEqual(with_eight, with_two)


class CloningPrimitiveTest(TestCase):
    """Unit tests for survey/cloning.py — clone_question and clone_section."""

    def setUp(self):
        self.org = _make_org()
        self.survey, self.section = _make_survey_with_section(self.org, 'cloning_src')
        self.question = Question.objects.create(
            survey_section=self.section,
            code='Q_orig_001',
            order_number=1,
            name='Address',
            input_type='text_line',
            validation_settings={'min_length': 5},
        )

    def test_clone_question_copies_validation_settings(self):
        """
        GIVEN a question with validation_settings={'min_length': 5}
        WHEN clone_question is called with regenerate_code=True
        THEN the cloned question has identical validation_settings
        """
        clone = clone_question(self.question, target_section=self.section, regenerate_code=True)
        self.assertEqual(clone.validation_settings, {'min_length': 5})

    def test_clone_question_regenerates_code(self):
        """
        GIVEN a question with code 'Q_orig_001'
        WHEN clone_question is called with regenerate_code=True
        THEN the cloned question has a different code
        """
        clone = clone_question(self.question, target_section=self.section, regenerate_code=True)
        self.assertNotEqual(clone.code, self.question.code)
        self.assertTrue(clone.code.startswith('Q_'))

    def test_clone_question_preserves_code_when_flag_false(self):
        """
        GIVEN a question
        WHEN clone_question is called with regenerate_code=False (versioning use case)
        THEN the cloned question has the SAME code as source
        """
        # Need a different target_section to avoid same-section, same-code conflict in tests.
        section_b = SurveySection.objects.create(
            survey_header=self.survey, name='sec_b', title='Section B', code='SB',
        )
        clone = clone_question(self.question, target_section=section_b, regenerate_code=False)
        self.assertEqual(clone.code, self.question.code)

    def test_clone_question_appends_name_suffix(self):
        """
        GIVEN a question named 'Address'
        WHEN clone_question is called with name_suffix=' (copy)'
        THEN the clone is named 'Address (copy)'
        """
        clone = clone_question(
            self.question, target_section=self.section, name_suffix=' (copy)',
        )
        self.assertEqual(clone.name, 'Address (copy)')

    def test_clone_question_with_subquestions(self):
        """
        GIVEN a point question with 2 sub-questions
        WHEN clone_question copies it with copy_sub_questions=True
        THEN the clone has 2 sub-questions, each with fresh codes
        """
        parent = Question.objects.create(
            survey_section=self.section, code='Q_parent_p',
            order_number=2, input_type='point', name='Locate',
        )
        sub1 = Question.objects.create(
            survey_section=self.section, parent_question_id=parent,
            code='Q_sub_a', order_number=1, input_type='text_line', name='Notes',
        )
        sub2 = Question.objects.create(
            survey_section=self.section, parent_question_id=parent,
            code='Q_sub_b', order_number=2, input_type='choice', name='Type',
        )
        clone = clone_question(parent, target_section=self.section, regenerate_code=True)
        clone_subs = list(Question.objects.filter(parent_question_id=clone).order_by('order_number'))
        self.assertEqual(len(clone_subs), 2)
        for orig, cloned in zip([sub1, sub2], clone_subs):
            self.assertNotEqual(orig.code, cloned.code)
            self.assertEqual(orig.name, cloned.name)

    def test_clone_question_drops_subquestions_when_flag_false(self):
        """
        GIVEN a point question with sub-questions
        WHEN clone_question is called with copy_sub_questions=False
        THEN the clone has zero sub-questions (used for paste-as-sub-question)
        """
        parent = Question.objects.create(
            survey_section=self.section, code='Q_parent_p2',
            order_number=2, input_type='point',
        )
        Question.objects.create(
            survey_section=self.section, parent_question_id=parent,
            code='Q_dropped', order_number=1, input_type='text_line',
        )
        clone = clone_question(
            parent, target_section=self.section,
            regenerate_code=True, copy_sub_questions=False,
        )
        self.assertEqual(Question.objects.filter(parent_question_id=clone).count(), 0)

    def test_clone_question_copies_translations(self):
        """
        GIVEN a question with QuestionTranslation rows for en and ru
        WHEN clone_question is called
        THEN the clone has equivalent translation rows (untouched name/subtext)
        """
        QuestionTranslation.objects.create(
            question=self.question, language='ru', name='Адрес', subtext='Полный адрес'
        )
        clone = clone_question(self.question, target_section=self.section, name_suffix=' (copy)')
        ru = QuestionTranslation.objects.get(question=clone, language='ru')
        # Suffix is NOT applied to translations
        self.assertEqual(ru.name, 'Адрес')
        self.assertEqual(ru.subtext, 'Полный адрес')

    def test_clone_section_appends_at_tail_when_insert_after_none(self):
        """
        GIVEN a survey with sections [A, B] in linked list and an unrelated source section
        WHEN clone_section is called with insert_after=None
        THEN the clone is appended at the tail
        """
        section_b = SurveySection.objects.create(
            survey_header=self.survey, name='b', title='B', code='SB',
        )
        self.section.next_section = section_b
        self.section.save(update_fields=['next_section'])
        section_b.prev_section = self.section
        section_b.save(update_fields=['prev_section'])

        source = SurveySection.objects.create(
            survey_header=self.survey, name='src', title='Source', code='SRC',
        )
        clone = clone_section(source, target_survey=self.survey, insert_after=None)
        clone.refresh_from_db()
        # Tail before clone was section_b OR source (whichever has next=None). The deduper
        # only computes new_name; the splice should pick the actual tail.
        section_b.refresh_from_db()
        # In this fixture section_b is the tail of the head→A→B chain. After clone,
        # source still has next=None too (it was a standalone section). The splice helper
        # picks ONE tail (the first match). Either section_b or source could be the tail.
        # Test the invariant: clone's prev_section is some real tail, clone has no next.
        self.assertIsNone(clone.next_section_id)
        self.assertIsNotNone(clone.prev_section_id)

    def test_clone_section_inserts_after_middle_section(self):
        """
        GIVEN sections linked [A, B, C]
        WHEN clone_section is called with insert_after=B
        THEN linked list becomes [A, B, B', C] with prev/next correctly stitched
        """
        section_b = SurveySection.objects.create(
            survey_header=self.survey, name='b', title='B', code='SB',
        )
        section_c = SurveySection.objects.create(
            survey_header=self.survey, name='c', title='C', code='SC',
        )
        # Link A → B → C
        self.section.next_section = section_b
        self.section.save()
        section_b.prev_section = self.section
        section_b.next_section = section_c
        section_b.save()
        section_c.prev_section = section_b
        section_c.save()

        clone = clone_section(
            section_b, target_survey=self.survey, insert_after=section_b, name_suffix=' (copy)',
        )
        clone.refresh_from_db()
        section_b.refresh_from_db()
        section_c.refresh_from_db()
        self.assertEqual(section_b.next_section_id, clone.id)
        self.assertEqual(clone.prev_section_id, section_b.id)
        self.assertEqual(clone.next_section_id, section_c.id)
        self.assertEqual(section_c.prev_section_id, clone.id)
        self.assertFalse(clone.is_head)
        self.assertEqual(clone.title, 'B (copy)')

    def test_clone_section_dedups_name(self):
        """
        GIVEN target survey already has a section with name 'sec_a'
        WHEN clone_section is called with a source whose name is 'sec_a'
        THEN the clone's name is 'sec_a_2'
        """
        # Clone section_a back into the same survey
        clone = clone_section(self.section, target_survey=self.survey)
        self.assertEqual(clone.name, 'sec_a_2')

    def test_clone_section_clones_questions_and_translations(self):
        """
        GIVEN a section with 2 questions and a translation
        WHEN clone_section is called
        THEN the clone has 2 questions (with new codes) and the translation row
        """
        SurveySectionTranslation.objects.create(
            section=self.section, language='ru', title='Раздел A',
        )
        Question.objects.create(
            survey_section=self.section, code='Q_q1', order_number=2,
            name='Q1', input_type='text_line',
        )
        clone = clone_section(self.section, target_survey=self.survey, name_suffix=' (copy)')
        self.assertEqual(
            Question.objects.filter(survey_section=clone, parent_question_id__isnull=True).count(),
            2,  # original Address + the Q1 we just added
        )
        self.assertTrue(
            SurveySectionTranslation.objects.filter(section=clone, language='ru').exists()
        )
        self.assertEqual(clone.title, 'Section A (copy)')


class EditorQuestionDuplicateTest(TestCase):
    """Tests for editor_question_duplicate (issue #16)."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor16q', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor16q', password='pass')
        self.survey, self.section = _make_survey_with_section(self.org, 'dup_q', owner=self.user)
        self.q1 = Question.objects.create(
            survey_section=self.section, code='Q_aa', order_number=1,
            name='First', input_type='text_line', validation_settings={'min_length': 3},
        )
        self.q2 = Question.objects.create(
            survey_section=self.section, code='Q_bb', order_number=2,
            name='Second', input_type='text_line',
        )

    def test_duplicate_creates_sibling_with_copy_suffix(self):
        """
        GIVEN a question 'First' at order_number=1 with sibling 'Second' at 2
        WHEN the user POSTs to editor_question_duplicate for 'First'
        THEN a clone with name 'First (copy)' appears at order_number=2
             AND 'Second' is shifted to order_number=3
             AND the clone has a fresh code
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.q1.id}/duplicate/',
        )
        self.assertEqual(response.status_code, 200)
        self.q2.refresh_from_db()
        self.assertEqual(self.q2.order_number, 3)
        clone = Question.objects.get(name='First (copy)')
        self.assertEqual(clone.order_number, 2)
        self.assertEqual(clone.validation_settings, {'min_length': 3})
        self.assertNotEqual(clone.code, self.q1.code)

    def test_duplicate_blocked_on_published_survey(self):
        """
        GIVEN a published survey
        WHEN duplicate is attempted on one of its questions
        THEN the response is 403 and no clone is created
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        before_count = Question.objects.filter(survey_section=self.section).count()
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.q1.id}/duplicate/',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            Question.objects.filter(survey_section=self.section).count(), before_count
        )


class EditorSectionDuplicateTest(TestCase):
    """Tests for editor_section_duplicate."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor16s', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor16s', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='dup_section', visibility='private', organization=self.org,
            created_by=self.user,
        )
        self.s_a = SurveySection.objects.create(
            survey_header=self.survey, name='a', title='A', code='SA', is_head=True,
        )
        self.s_b = SurveySection.objects.create(
            survey_header=self.survey, name='b', title='B', code='SB',
        )
        self.s_c = SurveySection.objects.create(
            survey_header=self.survey, name='c', title='C', code='SC',
        )
        self.s_a.next_section = self.s_b
        self.s_a.save()
        self.s_b.prev_section = self.s_a
        self.s_b.next_section = self.s_c
        self.s_b.save()
        self.s_c.prev_section = self.s_b
        self.s_c.save()
        Question.objects.create(
            survey_section=self.s_b, code='Q_b1', order_number=1,
            name='B-Q1', input_type='text_line',
        )

    def test_duplicate_inserts_after_source_in_linked_list(self):
        """
        GIVEN linked list [A, B, C]
        WHEN section B is duplicated
        THEN list becomes [A, B, B', C] with B'.title='B (copy)'
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.s_b.id}/duplicate/',
        )
        self.assertEqual(response.status_code, 200)
        clone = SurveySection.objects.get(title='B (copy)')
        self.s_b.refresh_from_db()
        self.s_c.refresh_from_db()
        self.assertEqual(self.s_b.next_section_id, clone.id)
        self.assertEqual(clone.prev_section_id, self.s_b.id)
        self.assertEqual(clone.next_section_id, self.s_c.id)
        self.assertEqual(self.s_c.prev_section_id, clone.id)
        # Question cloned
        self.assertEqual(
            Question.objects.filter(survey_section=clone).count(), 1
        )


class EditorQuestionPasteTest(TestCase):
    """Tests for editor_question_paste — same/cross survey, sub-question rules."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor16p', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor16p', password='pass')

        self.src_survey, self.src_section = _make_survey_with_section(
            self.org, 'src_paste', owner=self.user
        )
        self.src_q = Question.objects.create(
            survey_section=self.src_section, code='Q_src1', order_number=1,
            name='Source Q', input_type='text_line',
        )

        self.tgt_survey, self.tgt_section = _make_survey_with_section(
            self.org, 'tgt_paste', owner=self.user
        )

    def _post(self, body):
        return self.client.post(
            f'/editor/surveys/{self.tgt_survey.uuid}/sections/{self.tgt_section.id}/paste-question/',
            data=json.dumps(body),
            content_type='application/json',
        )

    def test_paste_cross_survey(self):
        """
        GIVEN user has editor on source and target surveys
        WHEN paste is invoked with the source question
        THEN a clone appears in the target section with a new code
        """
        response = self._post({
            'source_survey_uuid': str(self.src_survey.uuid),
            'source_question_id': self.src_q.id,
        })
        self.assertEqual(response.status_code, 200)
        clone = Question.objects.filter(survey_section=self.tgt_section).first()
        self.assertIsNotNone(clone)
        self.assertEqual(clone.name, 'Source Q')
        self.assertNotEqual(clone.code, self.src_q.code)

    def test_paste_geo_question_as_subquestion_rejected(self):
        """
        GIVEN clipboard holds a polygon question
        WHEN paste is invoked with a sub-question target (parent_question_id set)
        THEN the response is 400 and no Question is created
        """
        geo_src = Question.objects.create(
            survey_section=self.src_section, code='Q_geo', order_number=2,
            name='Region', input_type='polygon',
        )
        # Add a polygon parent in target so parent_question_id resolves
        target_parent = Question.objects.create(
            survey_section=self.tgt_section, code='Q_tgt_parent', order_number=1,
            name='TargetParent', input_type='polygon',
        )
        before_count = Question.objects.filter(survey_section=self.tgt_section).count()
        response = self._post({
            'source_survey_uuid': str(self.src_survey.uuid),
            'source_question_id': geo_src.id,
            'parent_question_id': target_parent.id,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Question.objects.filter(survey_section=self.tgt_section).count(),
            before_count,
        )

    def test_paste_subquestion_into_section_promotes_to_top_level(self):
        """
        GIVEN a sub-question (parent_question_id set) in the clipboard
        WHEN paste is invoked at the section top level (no parent_question_id)
        THEN the clone has parent_question_id=None
        """
        parent = Question.objects.create(
            survey_section=self.src_section, code='Q_parent2',
            order_number=2, input_type='point',
        )
        sub_src = Question.objects.create(
            survey_section=self.src_section, parent_question_id=parent,
            code='Q_subsrc', order_number=1, input_type='text_line', name='Note',
        )
        response = self._post({
            'source_survey_uuid': str(self.src_survey.uuid),
            'source_question_id': sub_src.id,
        })
        self.assertEqual(response.status_code, 200)
        promoted = Question.objects.filter(survey_section=self.tgt_section, name='Note').first()
        self.assertIsNotNone(promoted)
        self.assertIsNone(promoted.parent_question_id_id)


class EditorSectionPasteTest(TestCase):
    """Tests for editor_section_paste."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor16ps', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor16ps', password='pass')
        self.src_survey, self.src_section = _make_survey_with_section(
            self.org, 'src_psec', owner=self.user
        )
        Question.objects.create(
            survey_section=self.src_section, code='Q_psec_q', order_number=1,
            name='Source Question', input_type='text_line',
        )
        self.tgt_survey = SurveyHeader.objects.create(
            name='tgt_psec', visibility='private', organization=self.org,
            created_by=self.user,
        )
        self.tgt_section = SurveySection.objects.create(
            survey_header=self.tgt_survey, name='existing', title='Existing',
            code='EX', is_head=True,
        )

    def test_paste_section_appends_to_target(self):
        """
        GIVEN target survey with one head section
        WHEN a section is pasted from another survey
        THEN the clone is appended after the existing tail with the source's question
        """
        response = self.client.post(
            f'/editor/surveys/{self.tgt_survey.uuid}/paste-section/',
            data=json.dumps({
                'source_survey_uuid': str(self.src_survey.uuid),
                'source_section_id': self.src_section.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        # Two sections in target now: existing + clone
        self.assertEqual(SurveySection.objects.filter(survey_header=self.tgt_survey).count(), 2)
        clone = SurveySection.objects.filter(survey_header=self.tgt_survey).exclude(
            pk=self.tgt_section.pk
        ).first()
        self.assertIsNotNone(clone)
        self.assertEqual(
            Question.objects.filter(survey_section=clone, name='Source Question').count(), 1
        )

    def test_paste_section_blocked_on_published_target(self):
        """
        GIVEN target survey is published
        WHEN paste-section is invoked
        THEN the response is 403 and no section is created
        """
        self.tgt_survey.status = 'published'
        self.tgt_survey.save(update_fields=['status'])
        before_count = SurveySection.objects.filter(survey_header=self.tgt_survey).count()
        response = self.client.post(
            f'/editor/surveys/{self.tgt_survey.uuid}/paste-section/',
            data=json.dumps({
                'source_survey_uuid': str(self.src_survey.uuid),
                'source_section_id': self.src_section.id,
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            SurveySection.objects.filter(survey_header=self.tgt_survey).count(), before_count
        )


class EditorPreviewFinishButtonTest(TestCase):
    """The editor section preview shows navigation that makes sense without a live session."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username="prevu", password="pass")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.client.login(username="prevu", password="pass")
        self.survey = SurveyHeader.objects.create(
            name="prev_survey", visibility="private", organization=self.org,
        )
        self.only_section = SurveySection.objects.create(
            survey_header=self.survey, name="only", title="Only", code="O1", is_head=True,
        )

    def test_last_section_preview_shows_disabled_finish(self):
        """
        GIVEN a single-section survey previewed in the editor
        WHEN the last section renders in preview mode
        THEN a disabled Finish button is shown (not a live submit)
        """
        response = self.client.get(f"/editor/surveys/{self.survey.uuid}/preview/only/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("disabled", html)
        self.assertIn("Finish", html)
        # preview must not offer a real submit button for the last section
        self.assertNotIn('type="submit" class="btn btn-primary next_button"', html)

    def test_non_last_section_preview_links_to_next(self):
        """
        GIVEN a two-section survey previewed in the editor
        WHEN the first section renders in preview mode
        THEN Next is a link to the next section's preview, not a submit
        """
        second = SurveySection.objects.create(
            survey_header=self.survey, name="two", title="Two", code="O2",
        )
        self.only_section.next_section = second
        self.only_section.save(update_fields=["next_section"])
        second.prev_section = self.only_section
        second.save(update_fields=["prev_section"])

        html = self.client.get(f"/editor/surveys/{self.survey.uuid}/preview/only/").content.decode()
        self.assertIn("preview/two/", html)


@override_settings(MOBILE_EDITOR_NAV=False)
class SurveyNavScriptsTest(TestCase):
    """Every page rendering the survey nav must define the nav's click handler.

    `_survey_nav_tabs.html` wires Share and Preview to `onclick="navMenuToggle"`,
    which lives in `_lifecycle_scripts.html`. Share and Settings never included
    it, so both buttons threw ReferenceError and opened nothing (PostHog issue
    01a02d79, 2026-08-23).

    The flag is pinned OFF here on purpose. Later the same day, commit 928e927
    stopped rendering those dropdowns outside the Responses tab whenever
    MOBILE_EDITOR_NAV is on -- which is the default -- so the symptom vanished
    by accident rather than by repair. Setting the flag to False is the
    documented rollback path, and on that path the dead buttons are live again.
    Testing with the default would assert nothing.

    Asserted on rendered markup because a Django test that only checks the
    button exists stays green either way.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='nav_owner', password='pass')
        self.org = _make_org('NavOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="nav_survey", organization=self.org)
        SurveySection.objects.create(
            survey_header=self.survey, name="sec", code="S1", is_head=True)
        self.client.login(username='nav_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _assert_handler_defined(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        body = response.content.decode()
        self.assertIn('navMenuToggle(this,event)', body)
        self.assertIn('function navMenuToggle', body)

    def test_share_page_defines_the_nav_handler(self):
        """
        GIVEN the Share page, which renders the survey nav
        WHEN it is loaded
        THEN navMenuToggle is defined on the page, not only referenced
        """
        self._assert_handler_defined(f'/editor/surveys/{self.survey.uuid}/share/')

    def test_settings_page_defines_the_nav_handler(self):
        """
        GIVEN the survey Settings page, which renders the survey nav
        WHEN it is loaded
        THEN navMenuToggle is defined on the page, not only referenced
        """
        self._assert_handler_defined(f'/editor/surveys/{self.survey.uuid}/settings/')

    def test_build_page_still_defines_the_nav_handler(self):
        """
        GIVEN the Build page, which already included the scripts
        WHEN it is loaded
        THEN the handler is defined exactly as before
        """
        self._assert_handler_defined(f'/editor/surveys/{self.survey.uuid}/')


class EditorMapPickerSearchTest(TestCase):
    """Every editor map picker carries the shared place search
    (openspec: editor-map-picker-search) and the desktop sizing hooks."""

    def setUp(self):
        self.user = User.objects.create_user(username='picker_owner', password='pass')
        self.org = _make_org('PickerOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='picker_survey', organization=self.org,
            start_map_postion=Point(13.4050, 52.5231), start_map_zoom=12,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.client.login(username='picker_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_settings_page_has_search_above_a_wide_picker(self):
        """
        GIVEN the standalone survey settings page
        WHEN it renders
        THEN one search container precedes the map picker, the section is
             marked wide, and the picker carries the page sizing class
        """
        html = self.client.get(reverse('editor_survey_settings', args=[self.survey.uuid])).content.decode()

        self.assertEqual(html.count('id="survey-map-search"'), 1)
        self.assertLess(html.index('id="survey-map-search"'), html.index('id="survey-map-picker"'))
        self.assertIn('settings-section--wide', html)
        self.assertIn('class="picker-map picker-map--page"', html)
        self.assertIn("container: document.getElementById('survey-map-search')", html)
        # The base template ships the control for every editor page
        # (hashed by the manifest storage, hence the pattern).
        self.assertRegex(html, r'js/components/map_place_search(\.[0-9a-f]+)?\.js')

    def test_settings_panel_has_search_above_the_picker(self):
        """
        GIVEN the in-editor settings panel fragment
        WHEN it renders
        THEN the search container precedes the picker and the panel sizing class is used
        """
        html = self.client.get(reverse('editor_survey_settings_panel', args=[self.survey.uuid])).content.decode()

        self.assertEqual(html.count('id="survey-map-search"'), 1)
        self.assertLess(html.index('id="survey-map-search"'), html.index('id="survey-map-picker"'))
        self.assertIn('class="picker-map picker-map--panel"', html)
        self.assertIn("container: document.getElementById('survey-map-search')", html)

    def test_section_modal_has_search_that_lifts_inherit(self):
        """
        GIVEN the section map picker modal
        WHEN it renders
        THEN the search container precedes the picker and selecting a result
             unchecks "Inherit position" before applying it
        """
        html = self.client.get(reverse('editor_section_map_picker', args=[self.survey.uuid, self.section.id])).content.decode()

        self.assertEqual(html.count('id="map-picker-search"'), 1)
        self.assertLess(html.index('id="map-picker-search"'), html.index('id="map-picker"'))
        self.assertIn('class="picker-map picker-map--modal"', html)
        self.assertIn("container: document.getElementById('map-picker-search')", html)
        # A search result is a creator gesture: the picker unticks Inherit and
        # the flight's moveend saves the centre (map-picker-centre-autosave).
        self.assertIn('onSelect: picker.touched', html)

    def test_section_picker_declares_the_token_it_uses(self):
        """
        GIVEN the section map picker modal
        WHEN it renders with a Mapbox token configured
        THEN the place search receives the token as a template literal and the
             script never reads a `mapboxAccessToken` global — the basemap partial
             it includes renamed its own global on 2026-09-14 and the picker died
             with a ReferenceError before binding Save
             (openspec: fix-section-map-picker-init)
        """
        with self.settings(MAPBOX_ACCESS_TOKEN='pk.test-token'):
            html = self.client.get(reverse('editor_section_map_picker', args=[self.survey.uuid, self.section.id])).content.decode()

        self.assertIn("accessToken: 'pk.test-token'", html)
        self.assertNotIn('mapboxAccessToken', html)

    def test_section_picker_attaches_before_the_search(self):
        """
        GIVEN the section map picker modal
        WHEN it renders
        THEN the position picker is attached exactly once, before
             MapPlaceSearch.attach, and nothing of it lives inside the search's
             options — a throw while attaching the search control then costs
             the search box, never the picker (openspec: fix-section-map-picker-init)
        """
        html = self.client.get(reverse('editor_section_map_picker', args=[self.survey.uuid, self.section.id])).content.decode()

        attach = html.index('MapPlaceSearch.attach(')
        self.assertEqual(html.count('MapPositionPicker.attach('), 1)
        self.assertLess(html.index('MapPositionPicker.attach('), attach)
        search_options = html[attach:html.index('}, 300);')]
        self.assertNotIn('MapPositionPicker', search_options)
        self.assertNotIn('addEventListener', search_options)

    def test_save_endpoint_is_unchanged(self):
        """
        GIVEN a position chosen by search and saved through the existing endpoint
        WHEN the survey map position is posted
        THEN it is stored exactly as a click-chosen one would be
        """
        response = self.client.post(
            reverse('editor_survey_map_position', args=[self.survey.uuid]),
            {'lat': '59.4370', 'lng': '24.7536', 'zoom': '12', 'use_geolocation': '0'},
        )
        self.assertIn(response.status_code, (200, 204))
        self.survey.refresh_from_db()
        self.assertAlmostEqual(self.survey.start_map_postion.y, 59.4370, places=4)
        self.assertAlmostEqual(self.survey.start_map_postion.x, 24.7536, places=4)
        self.assertEqual(self.survey.start_map_zoom, 12)


class EditorMapPickerCentreAutosaveTest(TestCase):
    """The three editor map pickers take the position from the CENTRE of the
    map and save every settled move (openspec: map-picker-centre-autosave).

    A creator set three sections to three districts and got the survey default
    on all three: the pickers only read a click, she dragged — the create
    page's model — and Save wrote the untouched default as her choice. The
    click handler, the Save button and the create-a-different-model-per-picker
    are gone; one module drives all three.
    """

    SURFACES = ('settings_page', 'settings_panel', 'section_modal')

    def setUp(self):
        self.user = User.objects.create_user(username='centre_owner', password='pass')
        self.org = _make_org('CentreOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='centre_survey', organization=self.org,
            start_map_postion=Point(13.4050, 52.5231), start_map_zoom=12,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.client.login(username='centre_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _html(self, surface):
        url = {
            'settings_page': reverse('editor_survey_settings', args=[self.survey.uuid]),
            'settings_panel': reverse('editor_survey_settings_panel', args=[self.survey.uuid]),
            'section_modal': reverse('editor_section_map_picker', args=[self.survey.uuid, self.section.id]),
        }[surface]
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, surface)
        return response.content.decode()

    def test_every_picker_is_centre_based_with_autosave_and_no_save_button(self):
        """
        GIVEN the settings page, the settings panel and the section modal
        WHEN each renders
        THEN each attaches MapPositionPicker once, binds no map click handler,
             carries an autosave indicator and no Save button
        """
        for surface in self.SURFACES:
            html = self._html(surface)
            self.assertEqual(html.count('MapPositionPicker.attach('), 1, surface)
            self.assertNotIn("map.on('click'", html, surface)
            self.assertIn('class="autosave-indicator"', html, surface)
            self.assertNotIn('id="save-map-position"', html, surface)
            self.assertNotIn('id="save-survey-map-position"', html, surface)
            self.assertNotIn('Click the map', html, surface)
            self.assertNotIn('Click on the map', html, surface)

    def test_section_modal_wires_inherit_and_the_section_fields(self):
        """
        GIVEN the section map picker modal
        WHEN it renders
        THEN the picker receives the Inherit checkbox with the survey default as
             the inherit target, posts the geolocation flag and basemap override
             with every save, and saves both on change
        """
        html = self._html('section_modal')
        self.assertIn("checkbox: document.getElementById('clear-position')", html)
        self.assertIn('lat: inheritLat, lng: inheritLng, zoom: inheritZoom', html)
        self.assertIn('use_geolocation:', html)
        self.assertIn('override_basemap:', html)
        self.assertIn("watch: [document.getElementById('use-geolocation'), document.getElementById('override-basemap')]", html)
        self.assertNotIn('id="save-map-position"', html)

    def test_module_is_served_by_the_editor_base(self):
        """
        GIVEN any editor page
        WHEN it renders
        THEN the picker module is loaded by editor_base.html, so the two
             pickers that arrive by HTMX swap find it (a script inside a swapped
             fragment is not reliably executed)
        """
        html = self._html('settings_page')
        self.assertRegex(html, r'js/map_position_picker(\.[0-9a-f]+)?\.js')

    @override_settings(EDITOR_AUTOSAVE=False)
    def test_indicator_styling_does_not_depend_on_the_question_autosave_flag(self):
        """
        GIVEN EDITOR_AUTOSAVE switched off
        WHEN an editor page renders
        THEN the .autosave-indicator rules are still present — the map pickers
             use the indicator unconditionally
        """
        html = self._html('settings_page')
        self.assertIn('.autosave-indicator[data-state="error"]', html)

    def test_section_endpoint_stores_a_centre_and_clears_on_inherit(self):
        """
        GIVEN the section map-position endpoint the picker posts to
        WHEN a centre is posted with clear_position=0, then clear_position=1
        THEN the section holds the centre and zoom, then holds nothing
        """
        url = reverse('editor_section_map_picker', args=[self.survey.uuid, self.section.id])
        response = self.client.post(url, {
            'clear_position': '0', 'lat': '42.84600', 'lng': '-2.67300', 'zoom': '14',
            'use_geolocation': '0', 'override_basemap': '',
        })
        self.assertEqual(response.status_code, 204)
        self.section.refresh_from_db()
        self.assertAlmostEqual(self.section.start_map_postion.y, 42.846, places=4)
        self.assertAlmostEqual(self.section.start_map_postion.x, -2.673, places=4)
        self.assertEqual(self.section.start_map_zoom, 14)

        response = self.client.post(url, {
            'clear_position': '1', 'lat': '42.84600', 'lng': '-2.67300', 'zoom': '14',
            'use_geolocation': '0', 'override_basemap': '',
        })
        self.assertEqual(response.status_code, 204)
        self.section.refresh_from_db()
        self.assertIsNone(self.section.start_map_postion)
        self.assertIsNone(self.section.start_map_zoom)



class MapPickerAutosaveTeardownGuardTest(SimpleTestCase):
    """The autosave must not fire against a panel that has been swapped away.

    #192 gave the three pickers a debounced autosave whose `extraFields()`
    dereferenced `document.getElementById(...).checked` with no guard. The
    editor's settings panel is an HTMX fragment, so when it was replaced before
    the debounce elapsed the element was gone, the callback threw, and the
    creator's map position was silently lost.

    The fix has two independent halves, and this asserts both, because either
    one alone is a trap:

      * teardown -- the picker stops itself, so nothing fires at a detached DOM;
      * refusal  -- a save whose fields cannot be read is ABANDONED, never sent
        with a substituted value. `el && el.checked ? '1' : '0'` looks like a
        guard and is worse than the crash: it posts a `use_geolocation` the
        creator never chose and persists it.

    There is no JavaScript test runner in this repository, so this reads the
    source. Behaviour is verified in a browser; what this catches is the NEXT
    call site, added by someone who did not read #192.
    """

    ASSETS = os.path.join(settings.BASE_DIR, 'survey', 'assets', 'js')
    TEMPLATES = os.path.join(settings.BASE_DIR, 'survey', 'templates')

    PICKER_SITES = (
        'editor/partials/survey_settings_panel.html',
        'editor/partials/section_map_picker.html',
        'editor/survey_settings.html',
    )

    EXTRA_FIELDS = re.compile(
        r'extraFields:\s*function\s*\([^)]*\)\s*\{(?P<body>.*?)\n\s{12}\},', re.S)

    def _picker_source(self):
        with open(os.path.join(self.ASSETS, 'map_position_picker.js'), encoding='utf-8') as fh:
            return fh.read()

    def test_picker_exposes_detach(self):
        """
        GIVEN the picker module
        WHEN its public surface is read
        THEN it returns a detach() that clears the pending timer
        """
        source = self._picker_source()
        self.assertIn('detach: detach', source)
        self.assertRegex(source, r'function detach\(\)\s*\{[^}]*clearTimeout\(timer\)')

    def test_save_refuses_to_fire_at_a_detached_container(self):
        """
        GIVEN a pending save whose map container has left the document
        WHEN save() runs
        THEN it returns without fetching

        Independent of the teardown hook on purpose: a hook that silently stops
        matching is how this defect comes back, and this is the net under it.
        """
        source = self._picker_source()
        self.assertIn('document.body.contains(map.getContainer())', source)

    def test_a_payload_that_cannot_be_built_is_not_sent(self):
        """
        GIVEN extraFields() that throws or returns null
        WHEN payload() runs
        THEN it yields null and save() abandons rather than substituting values
        """
        source = self._picker_source()
        self.assertIn('if (!extra) return null;', source)
        self.assertIn('if (!body) return;', source)

    def test_every_extra_fields_call_site_refuses_rather_than_guesses(self):
        """
        GIVEN each template that attaches a MapPositionPicker
        WHEN its extraFields() callback is read
        THEN every element it reads is null-checked and the callback returns
             null rather than a substituted value
        """
        offenders = []
        for rel in self.PICKER_SITES:
            path = os.path.join(self.TEMPLATES, rel)
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            found = self.EXTRA_FIELDS.search(body)
            self.assertIsNotNone(found, f'{rel}: no extraFields callback found')
            callback = found.group('body')
            reads = re.findall(r"getElementById\('([^']+)'\)", callback)
            self.assertTrue(reads, f'{rel}: extraFields reads no elements')
            if 'return null' not in callback:
                offenders.append(f'{rel}: extraFields substitutes a value instead of refusing')
                continue
            # Every element must be held in a variable and checked, never
            # dereferenced straight off getElementById().
            if re.search(r"getElementById\('[^']+'\)\s*\.(checked|value)", callback):
                offenders.append(f'{rel}: dereferences getElementById() without a null check')
        self.assertEqual(offenders, [], '\n  '.join(offenders))


class SettingsPanelValidationContractTest(TestCase):
    """The 400 contract the panel autosave reads (backlog #187).

    `panel_autosave.js` names the rejected field out of `errors`. If this view
    ever stopped sending a per-field map -- a bare 400, a flat string -- the
    client would silently fall back to "tap to retry" and the creator would be
    back to guessing. The client half cannot see that regression; this can.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='panel_owner', password='pass')
        self.org = _make_org('PanelOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='panel_survey', organization=self.org)
        self.client.login(username='panel_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_invalid_field_comes_back_named(self):
        """
        GIVEN an autosave POST that clears the required survey name
        WHEN the settings panel endpoint answers
        THEN the status is 400 and `errors` names that field with a message
        """
        response = self.client.post(
            reverse('editor_survey_settings_panel', args=[self.survey.uuid]),
            {'name': '', 'redirect_url': '#', 'visibility': 'private'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['ok'])
        self.assertIn('name', payload['errors'])
        self.assertTrue(payload['errors']['name'][0])

    def test_an_empty_redirect_url_is_not_an_error(self):
        """
        GIVEN a creator who cleared "Redirect URL" because they want none
        WHEN the panel autosaves
        THEN the save succeeds and the field is stored as the "#" sentinel

        This is the dead end behind backlog #187: the model defaults the field
        to "#" but is not blank=True, so the ModelForm made it required and
        EVERY autosave of the whole panel came back 400 until the creator
        guessed to type "#" back in.
        """
        response = self.client.post(
            reverse('editor_survey_settings_panel', args=[self.survey.uuid]),
            {'name': 'panel_survey', 'redirect_url': '', 'visibility': 'private'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, '#')

    def test_a_valid_save_answers_ok(self):
        """
        GIVEN a valid autosave POST
        WHEN the settings panel endpoint answers
        THEN it is 200 and the client's success path applies
        """
        response = self.client.post(
            reverse('editor_survey_settings_panel', args=[self.survey.uuid]),
            {'name': 'renamed_survey', 'redirect_url': 'https://example.org/thanks/', 'visibility': 'private'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.name, 'renamed_survey')


class PanelAutosaveErrorReportingTest(SimpleTestCase):
    """An autosaving panel must say WHICH field a save was refused for.

    Backlog #187. All three panels ended their save with
    `.catch(function(){ setStatus('error'); })`, throwing away the `errors` map
    the views send with a 400. A creator whose Redirect URL was rejected saw
    "Not saved — retry" naming no field; retrying re-posted the same value, so
    the state never cleared. Replay Vision scored that session 4.0/10
    frustration on 2026-09-21 (Resilient Cities Network, user 413).

    There is no JavaScript test runner in this repository, so this reads the
    source. Behaviour is verified in a browser; what this catches is the FOURTH
    panel, added by someone who copied the inline autosaver that used to be
    here — which is exactly how #180 reached a fourth template six days after a
    fix covered three.
    """

    ASSETS = os.path.join(settings.BASE_DIR, 'survey', 'assets', 'js')
    TEMPLATES = os.path.join(settings.BASE_DIR, 'survey', 'templates')

    PANELS = (
        'editor/partials/survey_settings_panel.html',
        'editor/partials/thanks_panel.html',
        'editor/public_results.html',
    )

    def _module(self):
        with open(os.path.join(self.ASSETS, 'panel_autosave.js'), encoding='utf-8') as fh:
            return fh.read()

    def _panel(self, rel):
        with open(os.path.join(self.TEMPLATES, rel), encoding='utf-8') as fh:
            return fh.read()

    def test_validation_failure_names_the_field(self):
        """
        GIVEN the shared panel autosave module
        WHEN its failure path is read
        THEN a 400 carrying `errors` resolves the field's visible label and
             writes it into the status line
        """
        source = self._module()
        self.assertIn('resp.status !== 400', source)
        # The prefix is translatable (labels.notSaved); what must not drift is
        # that the message is built from the field's LABEL and its message.
        self.assertIn("labels.notSaved || 'Not saved'", source)
        self.assertIn("labelFor(form, name) + ': ' + message", source)
        self.assertIn("label[for=", source)

    def test_only_a_transport_failure_offers_a_retry(self):
        """
        GIVEN the shared panel autosave module
        WHEN the retry affordance is read
        THEN the click handler fires only in the retryable state, and only a
             transport failure sets it
        """
        source = self._module()
        self.assertIn("if (state === 'error-transport') statusEl.classList.add('is-retryable')", source)
        self.assertIn("if (statusEl.classList.contains('is-retryable')) saveNow();", source)
        # A validation failure must not be clickable: re-posting the same
        # rejected value fails identically and teaches the creator nothing.
        validation = source.split("error-validation")[1]
        self.assertNotIn('is-retryable', validation.split('function')[0])

    def test_a_success_clears_what_a_failure_marked(self):
        """
        GIVEN the shared panel autosave module
        WHEN a save succeeds
        THEN the invalid marks it set are cleared before the saved state
        """
        source = self._module()
        success = source.split('if (!resp.ok) return reportFailure(resp);')[1]
        self.assertIn('clearMarks();', success.split('function schedule')[0])

    def test_question_autosave_ignores_panel_forms(self):
        """
        GIVEN editor_autosave.js, which saves question EDIT forms
        WHEN its attach() is read
        THEN it skips a form without hx-post

        This is the root cause behind backlog #187. `data-autosave` is not this
        module's marker alone -- the editor panels carry it too -- so every
        keystroke in Survey settings also fired a question autosave, which
        POSTed to the string "null" (404) and wrote "Not saved — tap to retry"
        into the first `.autosave-indicator` in the form. On the settings panel
        that element is the MAP's indicator, so the error appeared under
        whatever control the creator had just touched, and no edit cleared it.
        """
        with open(os.path.join(self.ASSETS, 'editor_autosave.js'), encoding='utf-8') as fh:
            source = fh.read()
        attach = source.split('function attach(root)')[1]
        self.assertIn("if (!form.getAttribute('hx-post')) return;", attach)

    def test_panels_and_question_forms_do_not_share_an_autosaver(self):
        """
        GIVEN the panels marked data-autosave
        WHEN their markup is read
        THEN none of them carries hx-post, so the question autosaver cannot
             claim them even if someone re-adds a broad selector
        """
        offenders = []
        for rel in self.PANELS:
            body = self._panel(rel)
            for match in re.finditer(r'<form[^>]*data-autosave[^>]*>', body):
                if 'hx-post' in match.group(0):
                    offenders.append(f'{rel}: a data-autosave panel form carries hx-post')
        self.assertEqual(offenders, [], '\n  '.join(offenders))

    def test_every_panel_uses_the_shared_module(self):
        """
        GIVEN each editor panel that autosaves
        WHEN its script is read
        THEN it calls PanelAutosave.attach and defines no autosave status
             handler of its own
        """
        offenders = []
        for rel in self.PANELS:
            body = self._panel(rel)
            if 'PanelAutosave.attach' not in body:
                offenders.append(f'{rel}: does not use PanelAutosave')
            if re.search(r"function setStatus\s*\(", body):
                offenders.append(f'{rel}: defines its own autosave status handler')
            if "setStatus('error')" in body or "setStatus(form, 'error')" in body:
                offenders.append(f'{rel}: swallows the failure reason')
        self.assertEqual(offenders, [], '\n  '.join(offenders))

    def test_module_is_loaded_for_every_editor_page(self):
        """
        GIVEN the editor base template
        WHEN its script tags are read
        THEN panel_autosave.js is loaded, so an HTMX-swapped panel finds it
        """
        base = self._panel('editor/editor_base.html')
        self.assertIn("js/panel_autosave.js", base)

    def test_auto_center_switch_does_not_fire_the_settings_autosave(self):
        """
        GIVEN the Survey settings panel
        WHEN the autosave exclusions are read
        THEN the auto-center switch is excluded, because it saves through
             MapPositionPicker and a settings validation error must not appear
             under the control the creator just touched
        """
        body = self._panel('editor/partials/survey_settings_panel.html')
        attach = body.split('PanelAutosave.attach')[1]
        self.assertIn('#survey-use-geolocation', attach.split('});')[0])
        self.assertIn('#ref-layers-card', attach.split('});')[0])


class QuestionDraftOnTypePickTest(TestCase):
    """New question = pick a type; the row exists from that moment and the modal
    is the edit modal (spec survey-editor "Question rows are created on type pick")."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.org = Organization.objects.create(name="Draft Org")
        self.survey = SurveyHeader.objects.create(name="draft_survey", organization=self.org, redirect_url="/t/", status='draft')
        self.section = SurveySection.objects.create(survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.owner = User.objects.create_user('draftowner', 'd@example.com', 'pw')
        Membership.objects.create(user=self.owner, organization=self.org, role='admin')
        self.client.login(username='draftowner', password='pw')
        self.create_url = reverse('editor_question_create', kwargs={'survey_uuid': self.survey.uuid, 'section_id': self.section.pk})

    def test_type_pick_creates_the_row_and_returns_the_edit_modal(self):
        """
        GIVEN an empty section
        WHEN the picker posts draft=1 with input_type=point
        THEN a nameless point question exists, the response is its edit modal with the sub-questions
             block and the draft marker, plus the list item out of band; a bogus type is a 400
        """
        r = self.client.post(self.create_url, {'draft': '1', 'input_type': 'point'}, HTTP_HX_REQUEST='true')
        self.assertEqual(r.status_code, 200)
        q = Question.objects.get(survey_section=self.section)
        self.assertEqual((q.input_type, q.name or ''), ('point', ''))
        html = r.content.decode()
        self.assertIn('data-draft-question="%d"' % q.pk, html)
        self.assertIn('id="fg-subquestions"', html)
        self.assertIn('hx-swap-oob="beforeend:#questions-list"', html)
        self.assertIn('data-question-id="%d"' % q.pk, html)
        self.assertEqual(r['HX-Trigger'], 'questionUpdated')
        self.assertEqual(self.client.post(self.create_url, {'draft': '1', 'input_type': 'bogus'}).status_code, 400)
        self.assertEqual(Question.objects.filter(survey_section=self.section).count(), 1)

    def test_type_pick_keeps_name_and_subtext_typed_before_it(self):
        """
        GIVEN the New question modal with Name and Subtext typed before any type is picked
        WHEN the picker posts draft=1 with those values
        THEN the created question carries them (subtext sanitised), the re-rendered modal shows
             the name and has no draft marker — closing the modal keeps a named question
        """
        r = self.client.post(self.create_url, {
            'draft': '1', 'input_type': 'text', 'name': '  Where do you live?  ',
            'subtext': '<p>Roughly</p><script>alert(1)</script>',
        }, HTTP_HX_REQUEST='true')
        self.assertEqual(r.status_code, 200)
        q = Question.objects.get(survey_section=self.section)
        self.assertEqual(q.name, 'Where do you live?')
        self.assertEqual(q.subtext, '<p>Roughly</p>')
        html = r.content.decode()
        self.assertIn('Where do you live?', html)
        self.assertNotIn('data-draft-question', html)

    def test_subquestion_added_and_deleted_inside_the_modal_updates_the_section_row(self):
        """
        GIVEN a point question P created from the picker
        WHEN a sub-question is created with return_to_parent=1, then deleted
        THEN each response carries P's section-list row out of band (replace, scoped to
             #questions-list) — first with the child, then without it
        """
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'point'})
        p = Question.objects.get(survey_section=self.section)
        r = self.client.post(reverse('editor_subquestion_create', kwargs={'survey_uuid': self.survey.uuid, 'parent_id': p.pk}),
                             {'name': 'Why here?', 'input_type': 'text', 'subtext': '', 'display_style': 'default',
                              'color': '#000000', 'choices_json': '[]', 'return_to_parent': '1'}, HTTP_HX_REQUEST='true')
        html = r.content.decode()
        self.assertIn('hx-swap-oob="outerHTML:#questions-list li[data-top-level][data-question-id=\'%d\']"' % p.pk, html)
        self.assertIn('id="fg-subquestions"', html)
        self.assertIn('Why here?', html.split('hx-swap-oob=', 1)[1])  # the section row carries the child
        sub = Question.objects.get(parent_question_id=p)
        r = self.client.post(reverse('editor_question_delete', kwargs={'survey_uuid': self.survey.uuid, 'question_id': sub.pk}))
        html = r.content.decode()
        self.assertIn('hx-swap-oob="outerHTML:#questions-list li[data-top-level][data-question-id=\'%d\']"' % p.pk, html)
        self.assertNotIn('Why here?', html)
        self.assertEqual(r['HX-Trigger'], 'questionUpdated')

    def test_subquestion_edit_answers_with_the_parents_row(self):
        """
        GIVEN a point question P with a text sub-question S
        WHEN S is autosaved through its edit endpoint, and P's edit modal renders
        THEN the response is P's section-list row (with S nested inside), and the modal forms of
             both P and S target P's top-level row in #questions-list
        """
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'point'})
        p = Question.objects.get(survey_section=self.section)
        s = Question.objects.create(survey_section=self.section, code='SUBX', name='Why?', input_type='text',
                                    parent_question_id=p, order_number=1)
        url = reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': s.pk})
        r = self.client.post(url, {'name': 'Why there?', 'input_type': 'text', 'subtext': '', 'display_style': 'default',
                                   'color': '#000000', 'choices_json': '[]', 'autosave': '1'})
        html = r.content.decode()
        self.assertTrue(html.lstrip().startswith('<li class="question-item" data-question-id="%d"' % p.pk))
        self.assertIn('data-question-id="%d"' % s.pk, html)
        self.assertIn('Why there?', html)
        self.assertIn("hx-target=\"#questions-list [data-top-level][data-question-id='%d']\"" % p.pk, self.client.get(url).content.decode())
        purl = reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': p.pk})
        self.assertIn("hx-target=\"#questions-list [data-top-level][data-question-id='%d']\"" % p.pk, self.client.get(purl).content.decode())

    def test_close_keeps_a_configured_draft_and_drops_an_empty_one(self):
        """
        GIVEN two unnamed drafts: one Objects question with a layer picked, one bare text question
        WHEN the modal's close handler posts delete with if_empty=1 for each
        THEN the configured one is kept (204) and the empty one is deleted (200)
        """
        layer = _objects_layer(self.survey, name="Bins")
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'layer_objects'})
        configured = Question.objects.get(survey_section=self.section)
        Question.objects.filter(pk=configured.pk).update(layer=layer)
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'text'})
        empty = Question.objects.get(survey_section=self.section, input_type='text')
        url = lambda q: reverse('editor_question_delete', kwargs={'survey_uuid': self.survey.uuid, 'question_id': q.pk})
        self.assertEqual(self.client.post(url(configured), {'if_empty': '1'}).status_code, 204)
        self.assertTrue(Question.objects.filter(pk=configured.pk).exists())
        self.assertEqual(self.client.post(url(empty), {'if_empty': '1'}).status_code, 200)
        self.assertFalse(Question.objects.filter(pk=empty.pk).exists())

    def test_close_keeps_a_nameless_draft_whose_body_was_written(self):
        """
        GIVEN a nameless Formatted Text draft whose whole content lives in subtext
        WHEN the modal's close handler posts delete with if_empty=1
        THEN the question is kept (204) with its body intact, because for `html` the name is an
             editor-only label and subtext is what the respondent reads
        """
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'html',
                                           'subtext': '<p>Takes about 5 minutes.</p>'})
        q = Question.objects.get(survey_section=self.section, input_type='html')
        self.assertEqual(q.name or '', '')
        url = reverse('editor_question_delete', kwargs={'survey_uuid': self.survey.uuid, 'question_id': q.pk})
        self.assertEqual(self.client.post(url, {'if_empty': '1'}).status_code, 204)
        q.refresh_from_db()
        self.assertIn('Takes about 5 minutes.', q.subtext)

    def test_close_drops_a_draft_whose_subtext_is_markup_without_text(self):
        """
        GIVEN a nameless draft whose subtext holds markup but no readable text
        WHEN the modal's close handler posts delete with if_empty=1
        THEN the draft is deleted (200), because an opened-and-cleared editor is not content
        """
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'text'})
        q = Question.objects.get(survey_section=self.section, input_type='text')
        Question.objects.filter(pk=q.pk).update(subtext='<p><br></p>')
        url = reverse('editor_question_delete', kwargs={'survey_uuid': self.survey.uuid, 'question_id': q.pk})
        self.assertEqual(self.client.post(url, {'if_empty': '1'}).status_code, 200)
        self.assertFalse(Question.objects.filter(pk=q.pk).exists())

    def test_named_question_loses_the_draft_marker(self):
        """
        GIVEN a draft question
        WHEN it is autosaved with a name and the modal re-renders
        THEN the form no longer carries data-draft-question, so closing keeps it
        """
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'text'})
        q = Question.objects.get(survey_section=self.section)
        url = reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': q.pk})
        self.client.post(url, {'name': 'Named now', 'input_type': 'text', 'subtext': '', 'display_style': 'default',
                               'color': '#000000', 'choices_json': '[]', 'autosave': '1'})
        html = self.client.get(url).content.decode()
        self.assertNotIn('data-draft-question', html)
        self.assertEqual(Question.objects.get(pk=q.pk).name, 'Named now')

    def test_subquestion_from_modal_returns_to_parent(self):
        """
        GIVEN a draft point question opened in the modal
        WHEN a sub-question is created with return_to_parent=1
        THEN the response is the parent's edit modal listing the new child, not the closing list item
        """
        self.client.post(self.create_url, {'draft': '1', 'input_type': 'point'})
        parent = Question.objects.get(survey_section=self.section)
        url = reverse('editor_subquestion_create', kwargs={'survey_uuid': self.survey.uuid, 'parent_id': parent.pk})
        html = self.client.get(url + '?return=modal').content.decode()
        self.assertIn('name="return_to_parent"', html)
        self.assertIn('Back to question', html)
        r = self.client.post(url, {'name': 'Why here?', 'input_type': 'text', 'subtext': '', 'display_style': 'default',
                                   'color': '#000000', 'choices_json': '[]', 'return_to_parent': '1'})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('id="fg-subquestions"', html)
        self.assertIn('Why here?', html)
        self.assertIn('data-draft-question="%d"' % parent.pk, html)
        self.assertEqual(r['HX-Trigger'], 'questionUpdated')
        self.assertEqual(Question.objects.filter(parent_question_id=parent).count(), 1)
