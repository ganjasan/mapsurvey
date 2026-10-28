"""Tests for the `audit-log` capability (openspec/specs/audit-log/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySession, Membership
from survey.models import AuditLog
from survey.tests.helpers import _make_org


class AuditLogTest(TestCase):
    """Tests for the append-only audit trail of editor operations."""

    def setUp(self):
        """Set up an owner with a survey."""
        self.client = Client()
        self.org = _make_org('AuditOrg')
        self.user = User.objects.create_user(username='audituser', password='testpass123')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="audit_test_survey", organization=self.org, status='published',
        )
        self.client.login(username='audituser', password='testpass123')

    def test_trash_restore_purge_write_audit(self):
        """
        GIVEN a survey
        WHEN it is trashed, restored, trashed again, and purged
        THEN each operation writes an audit row with the actor, and rows survive the purge
        """
        from survey.models import AuditLog

        self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.client.post(f'/editor/restore/{self.survey.uuid}/')
        self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.client.post(f'/editor/purge/{self.survey.uuid}/')

        actions = list(
            AuditLog.objects.filter(survey_uuid=self.survey.uuid)
            .order_by('created_at').values_list('action', flat=True)
        )
        self.assertEqual(actions, ['survey_trash', 'survey_restore', 'survey_trash', 'survey_purge'])
        # Rows reference the purged survey by value and keep the actor
        self.assertFalse(SurveyHeader.objects.filter(pk=self.survey.pk).exists())
        for entry in AuditLog.objects.filter(survey_uuid=self.survey.uuid):
            self.assertEqual(entry.actor, self.user)
            self.assertEqual(entry.survey_name, 'audit_test_survey')

    def test_status_transition_audited(self):
        """
        GIVEN a published survey
        WHEN the owner transitions it to closed
        THEN an audit row records the old and new status
        """
        from survey.models import AuditLog

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/', {'status': 'closed'},
        )

        self.assertIn(response.status_code, (204, 302))
        entry = AuditLog.objects.get(action='status_transition', survey_uuid=self.survey.uuid)
        self.assertEqual(entry.metadata, {'old_status': 'published', 'new_status': 'closed'})

    def test_clear_test_data_audited(self):
        """
        GIVEN a testing survey with sessions
        WHEN the owner publishes with clear_test_data
        THEN sessions are deleted and an audit row records the count
        """
        from survey.models import AuditLog

        self.survey.status = 'testing'
        self.survey.save(update_fields=['status'])
        SurveySession.objects.create(survey=self.survey)
        SurveySession.objects.create(survey=self.survey)

        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published', 'clear_test_data': 'true'},
        )

        self.assertFalse(SurveySession.objects.filter(survey=self.survey).exists())
        entry = AuditLog.objects.get(action='clear_test_data', survey_uuid=self.survey.uuid)
        self.assertEqual(entry.metadata['deleted_sessions'], 2)

    def test_password_operations_audited(self):
        """
        GIVEN a survey
        WHEN the owner sets and then removes a password
        THEN both operations write audit rows
        """
        from survey.models import AuditLog

        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/password/',
            {'action': 'set', 'password': 'secret1'},
        )
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/password/', {'action': 'remove'},
        )

        self.assertTrue(AuditLog.objects.filter(action='password_set', survey_uuid=self.survey.uuid).exists())
        self.assertTrue(AuditLog.objects.filter(action='password_remove', survey_uuid=self.survey.uuid).exists())

    def test_audit_helper_swallows_exceptions(self):
        """
        GIVEN a broken request object
        WHEN audit() is called with it
        THEN no exception propagates and no row is written
        """
        from survey.audit import audit as audit_fn
        from survey.models import AuditLog

        audit_fn(object(), 'survey_trash', self.survey)  # no .user attribute

        self.assertFalse(AuditLog.objects.filter(action='survey_trash').exists())
