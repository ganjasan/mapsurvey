"""Tests for the `survey-edit-recovery` capability (openspec/specs/survey-edit-recovery/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Membership
from survey.versioning import publish_draft
from survey.tests.helpers import _make_org


class ClosedSurveyEditPathTest(TestCase):
    """Getting back to editing from a read-only survey."""

    def setUp(self):
        self.org = _make_org('RecoveryOrg')
        self.user = User.objects.create_user('recoveryuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='recoveryuser', password='pass')

    def _survey(self, status='published', name=None):
        survey = SurveyHeader.objects.create(
            name=name or f'recovery_{status}_{id(self)}', organization=self.org,
            created_by=self.user, status=status,
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        return survey

    def _transition(self, survey, status):
        return self.client.post(
            f'/editor/surveys/{survey.uuid}/transition/', {'status': status},
        )

    def _create_draft(self, survey):
        return self.client.post(f'/editor/surveys/{survey.uuid}/create-draft/')

    # ── Draft copies from closed surveys ──────────────────────────────────

    def test_draft_copy_can_be_created_from_a_closed_survey(self):
        """
        GIVEN a closed survey with no draft copy
        WHEN the owner creates one
        THEN the draft exists and the closed survey is untouched
        """
        survey = self._survey(status='closed')

        response = self._create_draft(survey)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(survey.has_draft_copy())
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'closed')

    def test_closed_survey_banner_offers_the_route(self):
        """
        GIVEN a closed survey with responses and no draft copy
        WHEN the owner opens the editor
        THEN the read-only notice offers to create a draft copy
        """
        survey = self._survey(status='closed')
        SurveySession.objects.create(survey=survey)

        response = self.client.get(f'/editor/surveys/{survey.uuid}/')

        self.assertTrue(response.context['show_edit_published'])
        # Assert the route is offered, not the wording on the button. The label
        # has already differed between the read-only bar and the publishing
        # widget ("Draft new version" / "Create a draft to edit"), and pinning
        # copy here fails the test for a rewording that changes no behaviour.
        self.assertContains(
            response, reverse('editor_create_draft', args=[survey.uuid]),
        )

    def test_second_draft_copy_is_still_refused(self):
        """
        GIVEN a closed survey that already has a draft copy
        WHEN another is requested
        THEN it is refused
        """
        survey = self._survey(status='closed')
        self._create_draft(survey)

        response = self._create_draft(survey)

        self.assertEqual(response.status_code, 409)

    def test_publishing_a_draft_leaves_the_survey_closed(self):
        """
        GIVEN a closed survey whose draft copy has been edited
        WHEN the draft is published
        THEN the changes land, the version increases, and the survey stays
             closed — publishing must not silently reopen it to respondents
        """
        survey = self._survey(status='closed')
        session = SurveySession.objects.create(survey=survey)
        self._create_draft(survey)
        draft = survey.get_draft_copy()

        publish_draft(draft)

        survey.refresh_from_db()
        self.assertEqual(survey.status, 'closed')
        self.assertEqual(survey.version_number, 2)
        archived = SurveyHeader.objects.get(canonical_survey=survey, is_canonical=False)
        session.refresh_from_db()
        self.assertEqual(session.survey_id, archived.id)

    # ── Undoing a publish that collected nothing ──────────────────────────

    def test_published_survey_with_nothing_collected_returns_to_draft(self):
        """
        GIVEN a published survey nobody has answered
        WHEN the owner returns it to draft
        THEN it becomes editable again
        """
        survey = self._survey(status='published')

        response = self._transition(survey, 'draft')

        self.assertIn(response.status_code, (200, 302))
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'draft')

    def test_closed_survey_with_nothing_collected_returns_to_draft(self):
        """
        GIVEN a closed survey nobody has answered
        WHEN the owner returns it to draft
        THEN it becomes editable again
        """
        survey = self._survey(status='closed')

        self._transition(survey, 'draft')

        survey.refresh_from_db()
        self.assertEqual(survey.status, 'draft')

    def test_survey_with_responses_cannot_return_to_draft(self):
        """
        GIVEN a published survey that has collected a response
        WHEN the owner attempts to return it to draft
        THEN it is refused and the status is unchanged
        """
        survey = self._survey(status='published')
        SurveySession.objects.create(survey=survey)

        response = self._transition(survey, 'draft')

        self.assertEqual(response.status_code, 400)
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'published')

    def test_survey_whose_sessions_moved_to_an_archive_cannot_return_to_draft(self):
        """
        GIVEN a survey whose responses moved onto an archived version when a new
              version was published, leaving it with no sessions of its own
        WHEN the owner attempts to return it to draft
        THEN it is refused

        A plain session count would read this survey as untouched.
        """
        survey = self._survey(status='published')
        SurveySession.objects.create(survey=survey)
        self._create_draft(survey)
        publish_draft(survey.get_draft_copy())
        survey.refresh_from_db()
        self.assertEqual(SurveySession.objects.filter(survey=survey).count(), 0)

        response = self._transition(survey, 'draft')

        self.assertEqual(response.status_code, 400)
        survey.refresh_from_db()
        self.assertEqual(survey.status, 'published')

    def test_back_to_draft_is_not_offered_once_a_response_exists(self):
        """
        GIVEN a published survey with a response
        WHEN the owner opens the editor
        THEN the undo is not offered
        """
        survey = self._survey(status='published')
        SurveySession.objects.create(survey=survey)

        response = self.client.get(f'/editor/surveys/{survey.uuid}/')

        self.assertFalse(response.context['show_back_to_draft'])

    def test_back_to_draft_is_offered_when_nothing_collected(self):
        """
        GIVEN a published survey nobody has answered
        WHEN the owner opens the editor
        THEN the undo is offered
        """
        survey = self._survey(status='published')

        response = self.client.get(f'/editor/surveys/{survey.uuid}/')

        self.assertTrue(response.context['show_back_to_draft'])

    # ── The lock itself is unchanged ──────────────────────────────────────

    def test_structural_edits_are_still_blocked_on_a_closed_survey(self):
        """
        GIVEN a closed survey
        WHEN a question deletion is attempted directly
        THEN it is still refused by the read-only lock
        """
        survey = self._survey(status='closed')
        question = Question.objects.filter(survey_section__survey_header=survey).first()

        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/questions/{question.id}/delete/'
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Question.objects.filter(pk=question.pk).exists())


class HasNeverCollectedTest(TestCase):
    """The condition both new transitions depend on."""

    def setUp(self):
        self.org = _make_org('CollectedOrg')
        self.user = User.objects.create_user('collecteduser', password='pass')

    def _survey(self, name, status='published'):
        return SurveyHeader.objects.create(
            name=name, organization=self.org, created_by=self.user, status=status,
        )

    def test_fresh_survey_has_never_collected(self):
        """
        GIVEN a survey with no sessions and no versions
        WHEN the condition is evaluated
        THEN it is true
        """
        self.assertTrue(self._survey('fresh').has_never_collected())

    def test_survey_with_a_session_has_collected(self):
        """
        GIVEN a survey with one session
        WHEN the condition is evaluated
        THEN it is false
        """
        survey = self._survey('with_session')
        SurveySession.objects.create(survey=survey)

        self.assertFalse(survey.has_never_collected())

    def test_survey_with_an_archived_version_has_collected(self):
        """
        GIVEN a survey with no sessions of its own but an archived version
        WHEN the condition is evaluated
        THEN it is false — the sessions moved there when the version was published
        """
        survey = self._survey('with_history')
        SurveyHeader.objects.create(
            name='with_history_v1', organization=self.org, created_by=self.user,
            status='closed', is_canonical=False, canonical_survey=survey,
            version_number=1,
        )

        self.assertFalse(survey.has_never_collected())
