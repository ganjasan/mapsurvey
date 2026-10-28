"""Tests that no capability owns yet: survey-lifecycle-states.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Membership, SurveyCollaborator
from survey.tests.helpers import _make_org


class LifecycleTransitionTest(TestCase):
    """Tests for survey lifecycle state transitions."""

    def setUp(self):
        self.org = _make_org('LifecycleOrg')
        self.user = User.objects.create_user(username='lifecycle_user', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='lifecycle_test', organization=self.org, created_by=self.user,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q_LC1', name='Q1', input_type='text',
        )

    def test_new_survey_is_draft(self):
        """
        GIVEN a newly created survey
        WHEN checking status
        THEN it should be 'draft'
        """
        self.assertEqual(self.survey.status, 'draft')

    def test_valid_transitions_return_true(self):
        """
        GIVEN a survey in draft status with password and structure
        WHEN checking can_transition_to for valid targets
        THEN each should return (True, "")
        """
        self.survey.set_password('test1234')
        self.survey.save()
        ok, err = self.survey.can_transition_to('testing')
        self.assertTrue(ok)
        self.assertEqual(err, '')

        ok, err = self.survey.can_transition_to('published')
        self.assertTrue(ok)
        self.assertEqual(err, '')

    def test_invalid_transition_returns_error(self):
        """
        GIVEN a survey in draft status
        WHEN checking can_transition_to('closed')
        THEN it should return (False, error message)
        """
        ok, err = self.survey.can_transition_to('closed')
        self.assertFalse(ok)
        self.assertIn('Cannot transition', err)

    def test_archived_is_terminal(self):
        """
        GIVEN a survey in archived status
        WHEN checking can_transition_to for any target
        THEN all should return (False, error)
        """
        self.survey.status = 'archived'
        for target in ('draft', 'testing', 'published', 'closed'):
            ok, err = self.survey.can_transition_to(target)
            self.assertFalse(ok)
            self.assertIn('Cannot transition from archived', err)

    def test_draft_to_testing_without_password_allowed(self):
        """
        GIVEN a draft survey without password but with valid structure
        WHEN checking can_transition_to('testing')
        THEN it should succeed (password is optional)
        """
        ok, err = self.survey.can_transition_to('testing')
        self.assertTrue(ok)

    def test_draft_to_testing_requires_structure(self):
        """
        GIVEN a draft survey with no sections/questions
        WHEN checking can_transition_to('testing')
        THEN it should fail with structure required error
        """
        empty_survey = SurveyHeader.objects.create(
            name='empty', organization=self.org,
        )
        ok, err = empty_survey.can_transition_to('testing')
        self.assertFalse(ok)
        self.assertIn('section', err.lower())

    def test_draft_to_testing_requires_head_section(self):
        """
        GIVEN a draft survey with questions but no head section
        WHEN checking can_transition_to('testing')
        THEN it should fail with head section error
        """
        survey = SurveyHeader.objects.create(
            name='no_head', organization=self.org,
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='s1', code='S1', is_head=False,
        )
        Question.objects.create(
            survey_section=section, code='Q_NH1', name='Q1', input_type='text',
        )
        ok, err = survey.can_transition_to('testing')
        self.assertFalse(ok)
        self.assertIn('head section', err.lower())

    def test_draft_to_published_requires_structure(self):
        """
        GIVEN a draft survey with no structure
        WHEN checking can_transition_to('published')
        THEN it should fail with structure required error
        """
        empty_survey = SurveyHeader.objects.create(
            name='empty2', organization=self.org,
        )
        ok, err = empty_survey.can_transition_to('published')
        self.assertFalse(ok)
        self.assertIn('section', err.lower())


class EditorTransitionTest(TestCase):
    """Tests for the editor_survey_transition endpoint."""

    def setUp(self):
        self.org = _make_org('TransOrg')
        self.owner = User.objects.create_user(username='trans_owner', password='pass')
        self.editor = User.objects.create_user(username='trans_editor', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        self.survey = SurveyHeader.objects.create(
            name='trans_test', organization=self.org, created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q_TR1', name='Q1', input_type='text',
        )

    def test_valid_transition_returns_204(self):
        """
        GIVEN a draft survey with structure
        WHEN owner posts transition to published
        THEN status 204 and survey status updated
        """
        self.client.login(username='trans_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 204)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'published')

    def test_invalid_transition_returns_400(self):
        """
        GIVEN a draft survey
        WHEN owner posts transition to closed
        THEN status 400 with error message
        """
        self.client.login(username='trans_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'closed'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 400)

    def test_non_owner_returns_403(self):
        """
        GIVEN a draft survey
        WHEN editor (not owner) posts transition
        THEN status 403
        """
        self.client.login(username='trans_editor', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'},
        )
        self.assertEqual(response.status_code, 403)

    def test_test_data_cleanup(self):
        """
        GIVEN a testing survey with sessions
        WHEN owner transitions to published with clear_test_data=true
        THEN all sessions are deleted
        """
        self.survey.set_password('test1234')
        self.survey.status = 'testing'
        self.survey.save()
        SurveySession.objects.create(survey=self.survey)
        SurveySession.objects.create(survey=self.survey)
        self.assertEqual(SurveySession.objects.filter(survey=self.survey).count(), 2)

        self.client.login(username='trans_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published', 'clear_test_data': 'true'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(SurveySession.objects.filter(survey=self.survey).count(), 0)

    def test_archive_syncs_is_archived(self):
        """
        GIVEN a closed survey
        WHEN owner transitions to archived
        THEN is_archived is set to True
        """
        self.survey.status = 'closed'
        self.survey.save()
        self.client.login(username='trans_owner', password='pass')
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'archived'},
            HTTP_HX_REQUEST='true',
        )
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'archived')
        self.assertTrue(self.survey.is_archived)
