"""Tests for the `survey-version-restore` capability (openspec/specs/survey-version-restore/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.analytics import SurveyAnalyticsService
from survey.versioning import clone_survey_for_draft, publish_draft
from survey.tests.helpers import _make_org


class RestoreVersionTest(TestCase):
    """Restore an archived version's questionnaire as a new draft (rollback)."""

    def setUp(self):
        from survey.versioning import clone_survey_for_draft, publish_draft
        self.org = _make_org('RestoreOrg')
        self.owner = User.objects.create_user('restore_owner', password='pw')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='restore_survey', organization=self.org, created_by=self.owner,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, name='Keep', input_type='choice',
            code='QKEEP', order_number=1,
            choices=[{'code': 1, 'name': 'Yes'}],
        )
        self.q_drop = Question.objects.create(
            survey_section=self.section, name='Drop', input_type='text',
            code='QDROP', order_number=2,
        )
        self.v1_sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.v1_sess, question=self.q_drop,
                              text='precious history')

        # v2 drops QDROP
        draft = clone_survey_for_draft(self.survey)
        Question.objects.filter(survey_section__survey_header=draft, code='QDROP').delete()
        self.canonical = publish_draft(draft, force=True)

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _restore(self, version='v1'):
        return self.client.post(
            f'/editor/surveys/{self.canonical.uuid}/restore-version/',
            {'version': version},
        )

    def test_restore_creates_draft_with_old_structure(self):
        """
        GIVEN v1 (has QDROP) archived and v2 (no QDROP) current
        WHEN the owner restores v1
        THEN a draft linked to the canonical carries QDROP with its original code
        """
        self._login(self.owner)
        response = self._restore()
        self.assertEqual(response.status_code, 302)
        draft = self.canonical.get_draft_copy()
        self.assertIsNotNone(draft)
        codes = set(Question.objects.filter(
            survey_section__survey_header=draft,
        ).values_list('code', flat=True))
        self.assertEqual(codes, {'QKEEP', 'QDROP'})

    def test_restore_guards(self):
        """
        GIVEN various invalid preconditions
        WHEN restore is attempted
        THEN it is rejected and no draft appears
        """
        from survey.versioning import clone_survey_for_draft
        self._login(self.owner)
        # unknown version
        self.assertEqual(self._restore('v9').status_code, 404)
        # invalid version string
        self.assertEqual(self._restore('nonsense').status_code, 400)
        # draft already exists
        clone_survey_for_draft(self.canonical)
        self.assertEqual(self._restore('v1').status_code, 409)

    def test_restore_denied_for_non_owner_editor(self):
        """
        GIVEN a non-owner editor collaborator
        WHEN they attempt a restore
        THEN it is denied and no draft is created
        """
        editor = User.objects.create_user('restore_editor', password='pw')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.canonical, role='editor')
        self._login(editor)
        response = self._restore()
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(self.canonical.has_draft_copy())

    def test_publish_of_restored_draft_revives_lineage(self):
        """
        GIVEN QDROP archived with a v1 answer while v2 is current
        WHEN the owner restores v1 and publishes the draft
        THEN v3 is current, QDROP's lineage is current again and its
             historical answer reports without the archived badge
        """
        from survey.versioning import publish_draft
        from survey.analytics import SurveyAnalyticsService
        self._login(self.owner)
        self._restore()
        draft = self.canonical.get_draft_copy()
        canonical = publish_draft(draft, force=True)
        self.assertEqual(canonical.version_number, 3)

        stats = {s['question'].code: s
                 for s in SurveyAnalyticsService(canonical).get_all_question_stats()}
        drop = stats['QDROP']
        self.assertFalse(drop['archived'])
        self.assertEqual(drop['total_answers'], 1)   # the v1 answer is back

    def test_widget_shows_restore_only_when_available(self):
        """
        GIVEN a published survey with an archived v1
        WHEN the owner opens Build (widget rendered)
        THEN a Restore action is present — and disappears once a draft exists
        """
        from survey.versioning import clone_survey_for_draft
        self._login(self.owner)
        html = self.client.get(f'/editor/surveys/{self.canonical.uuid}/').content.decode()
        self.assertIn('restore-version', html)
        clone_survey_for_draft(self.canonical)
        html = self.client.get(f'/editor/surveys/{self.canonical.uuid}/').content.decode()
        self.assertNotIn('restore-version', html)
