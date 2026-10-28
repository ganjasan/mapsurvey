"""Tests that no capability owns yet: org-access-control.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from io import BytesIO
import json
import uuid
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership, SurveyCollaborator, Invitation
from survey.permissions import get_effective_survey_role
from django.test import RequestFactory
import os
import tempfile
from io import StringIO
from django.core.management import call_command
from django.contrib.auth.models import AnonymousUser
from survey.tests.helpers import _eager_import, _make_org


# ─── Task 2.6: Permission Resolution Logic Tests ────────────────────────────

class PermissionResolutionTest(TestCase):
    """Tests for permission resolution logic (org baseline + survey collaborator)."""

    def setUp(self):
        self.org = _make_org('PermOrg')
        self.survey = SurveyHeader.objects.create(name='perm_survey', organization=self.org)
        self.owner_user = User.objects.create_user(username='org_owner', password='pass')
        self.admin_user = User.objects.create_user(username='org_admin', password='pass')
        self.editor_user = User.objects.create_user(username='org_editor', password='pass')
        self.viewer_user = User.objects.create_user(username='org_viewer', password='pass')
        self.nonmember = User.objects.create_user(username='nonmember', password='pass')

        Membership.objects.create(user=self.owner_user, organization=self.org, role='owner')
        Membership.objects.create(user=self.admin_user, organization=self.org, role='admin')
        Membership.objects.create(user=self.editor_user, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer_user, organization=self.org, role='viewer')

    def test_org_owner_gets_survey_owner_role(self):
        """
        GIVEN an org owner with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is 'owner'
        """
        role = get_effective_survey_role(self.owner_user, self.survey)
        self.assertEqual(role, 'owner')

    def test_org_admin_gets_survey_owner_role(self):
        """
        GIVEN an org admin with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is 'owner' (admin maps to survey owner)
        """
        role = get_effective_survey_role(self.admin_user, self.survey)
        self.assertEqual(role, 'owner')

    def test_org_editor_gets_none_without_collaborator(self):
        """
        GIVEN an org editor with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is None (editor gets no implicit access to others' surveys)
        """
        role = get_effective_survey_role(self.editor_user, self.survey)
        self.assertIsNone(role)

    def test_org_editor_with_collaborator_gets_collaborator_role(self):
        """
        GIVEN an org editor who is a survey collaborator with 'editor' role
        WHEN get_effective_survey_role is called
        THEN effective role is 'editor'
        """
        SurveyCollaborator.objects.create(user=self.editor_user, survey=self.survey, role='editor')
        role = get_effective_survey_role(self.editor_user, self.survey)
        self.assertEqual(role, 'editor')

    def test_org_viewer_gets_viewer_baseline(self):
        """
        GIVEN an org viewer with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is 'viewer'
        """
        role = get_effective_survey_role(self.viewer_user, self.survey)
        self.assertEqual(role, 'viewer')

    def test_org_viewer_with_editor_collaborator_gets_editor(self):
        """
        GIVEN an org viewer who has an explicit 'editor' collaborator role
        WHEN get_effective_survey_role is called
        THEN effective role is 'editor' (max of viewer baseline and editor collab)
        """
        SurveyCollaborator.objects.create(user=self.viewer_user, survey=self.survey, role='editor')
        role = get_effective_survey_role(self.viewer_user, self.survey)
        self.assertEqual(role, 'editor')

    def test_org_viewer_with_owner_collaborator_gets_owner(self):
        """
        GIVEN an org viewer who has an explicit 'owner' collaborator role
        WHEN get_effective_survey_role is called
        THEN effective role is 'owner'
        """
        SurveyCollaborator.objects.create(user=self.viewer_user, survey=self.survey, role='owner')
        role = get_effective_survey_role(self.viewer_user, self.survey)
        self.assertEqual(role, 'owner')

    def test_nonmember_gets_none(self):
        """
        GIVEN a user who is not a member of the org
        WHEN get_effective_survey_role is called
        THEN effective role is None
        """
        role = get_effective_survey_role(self.nonmember, self.survey)
        self.assertIsNone(role)

    def test_unauthenticated_user_gets_none(self):
        """
        GIVEN an anonymous (unauthenticated) user object
        WHEN get_effective_survey_role is called
        THEN effective role is None
        """
        from django.contrib.auth.models import AnonymousUser
        role = get_effective_survey_role(AnonymousUser(), self.survey)
        self.assertIsNone(role)

    def test_org_editor_with_viewer_collaborator_gets_viewer(self):
        """
        GIVEN an org editor who has an explicit 'viewer' collaborator role
        WHEN get_effective_survey_role is called
        THEN effective role is 'viewer' (editor baseline is None, collab is viewer)
        """
        SurveyCollaborator.objects.create(user=self.editor_user, survey=self.survey, role='viewer')
        role = get_effective_survey_role(self.editor_user, self.survey)
        self.assertEqual(role, 'viewer')


# ─── Task 4.8: Organization CRUD and Member Management Tests ────────────────

class OrgCRUDTest(TestCase):
    """Tests for organization creation, settings, and member management."""

    def setUp(self):
        self.owner = User.objects.create_user(username='org_owner', password='pass')
        self.admin = User.objects.create_user(username='org_admin', password='pass')
        self.viewer = User.objects.create_user(username='org_viewer', password='pass')
        self.outsider = User.objects.create_user(username='outsider', password='pass')

        self.org = _make_org('TestCrudOrg')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

    def test_create_org_as_authenticated_user(self):
        """
        GIVEN an authenticated user
        WHEN they POST to org creation with a name
        THEN a new org is created and they become owner
        """
        self.client.login(username='outsider', password='pass')
        response = self.client.post('/org/new/', {'name': 'My New Org'})
        self.assertEqual(response.status_code, 302)
        org = Organization.objects.get(name='My New Org')
        self.assertTrue(Membership.objects.filter(user=self.outsider, organization=org, role='owner').exists())

    def test_create_org_unauthenticated_redirects(self):
        """
        GIVEN an unauthenticated user
        WHEN they access org creation
        THEN they are redirected to login
        """
        response = self.client.post('/org/new/', {'name': 'Nope'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_org_settings_owner_can_edit(self):
        """
        GIVEN an org owner
        WHEN they POST updated settings
        THEN the org is updated
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(f'/org/{self.org.slug}/settings/', {
            'name': 'Updated Name',
            'slug': self.org.slug,
        })
        self.assertEqual(response.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, 'Updated Name')

    def test_org_settings_non_owner_forbidden(self):
        """
        GIVEN an org admin (not owner)
        WHEN they access org settings
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.get(f'/org/{self.org.slug}/settings/')
        self.assertEqual(response.status_code, 403)

    def test_change_role_by_owner(self):
        """
        GIVEN an org owner
        WHEN they change a viewer's role to editor
        THEN the role is updated
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.viewer.id}/role/',
            {'role': 'editor'},
        )
        self.assertEqual(response.status_code, 302)
        m = Membership.objects.get(user=self.viewer, organization=self.org)
        self.assertEqual(m.role, 'editor')

    def test_admin_cannot_change_owner_role(self):
        """
        GIVEN an org admin
        WHEN they try to change an owner's role
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.owner.id}/role/',
            {'role': 'editor'},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_promote_to_owner(self):
        """
        GIVEN an org admin
        WHEN they try to promote a viewer to owner
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.viewer.id}/role/',
            {'role': 'owner'},
        )
        self.assertEqual(response.status_code, 403)

    def test_remove_member_by_owner(self):
        """
        GIVEN an org owner
        WHEN they remove a viewer member
        THEN the membership is deleted
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.viewer.id}/remove/',
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Membership.objects.filter(user=self.viewer, organization=self.org).exists())

    def test_cannot_remove_last_owner(self):
        """
        GIVEN only one owner in the org
        WHEN they try to remove themselves
        THEN the removal is rejected
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.owner.id}/remove/',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Membership.objects.filter(user=self.owner, organization=self.org).exists())

    def test_admin_cannot_remove_owner(self):
        """
        GIVEN an org admin
        WHEN they try to remove an owner
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.owner.id}/remove/',
        )
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_view_members(self):
        """
        GIVEN a user not in the org
        WHEN they try to view members
        THEN they get 403
        """
        self.client.login(username='outsider', password='pass')
        response = self.client.get(f'/org/{self.org.slug}/members/')
        self.assertEqual(response.status_code, 403)

    def test_viewer_can_view_members(self):
        """
        GIVEN an org viewer
        WHEN they view the members page
        THEN they get 200
        """
        self.client.login(username='org_viewer', password='pass')
        response = self.client.get(f'/org/{self.org.slug}/members/')
        self.assertEqual(response.status_code, 200)


# ─── Task 5.8: Invitation Tests ─────────────────────────────────────────────

class InvitationTest(TestCase):
    """Tests for the invitation system."""

    def setUp(self):
        self.org = _make_org('InviteOrg')
        self.owner = User.objects.create_user(username='inv_owner', password='pass')
        self.admin = User.objects.create_user(username='inv_admin', password='pass')
        self.existing_user = User.objects.create_user(username='existing', password='pass', email='existing@test.com')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')

    def test_send_invitation_as_owner(self):
        """
        GIVEN an org owner
        WHEN they send an invitation to an email
        THEN an Invitation record is created
        """
        self.client.login(username='inv_owner', password='pass')
        response = self.client.post(f'/org/{self.org.slug}/invite/', {
            'email': 'newuser@test.com',
            'role': 'editor',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Invitation.objects.filter(email='newuser@test.com', organization=self.org).exists())

    def test_send_invitation_admin_cannot_invite_as_owner(self):
        """
        GIVEN an org admin
        WHEN they try to send an invitation with role 'owner'
        THEN the invitation is not created (admin cannot invite owners)
        """
        self.client.login(username='inv_admin', password='pass')
        response = self.client.post(f'/org/{self.org.slug}/invite/', {
            'email': 'newowner@test.com',
            'role': 'owner',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Invitation.objects.filter(email='newowner@test.com', role='owner').exists())

    def test_accept_invitation_as_existing_user(self):
        """
        GIVEN an existing user and a pending invitation
        WHEN they visit the accept URL
        THEN they are added to the org
        """
        invitation = Invitation.objects.create(
            email='existing@test.com', organization=self.org, role='editor', invited_by=self.owner,
        )
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Membership.objects.filter(user=self.existing_user, organization=self.org, role='editor').exists())
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)

    def test_accept_already_used_invitation(self):
        """
        GIVEN an invitation that has already been accepted
        WHEN a user visits the accept URL
        THEN they see an info message and are redirected
        """
        from django.utils import timezone
        invitation = Invitation.objects.create(
            email='existing@test.com', organization=self.org, role='editor',
            invited_by=self.owner, accepted_at=timezone.now(),
        )
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)

    def test_accept_expired_invitation(self):
        """
        GIVEN an invitation older than 7 days
        WHEN a user visits the accept URL
        THEN they see an error and are redirected
        """
        from django.utils import timezone
        from datetime import timedelta
        invitation = Invitation.objects.create(
            email='existing@test.com', organization=self.org, role='editor', invited_by=self.owner,
        )
        # Manually backdate the created_at
        Invitation.objects.filter(pk=invitation.pk).update(created_at=timezone.now() - timedelta(days=8))
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)
        # User should NOT be added to org
        self.assertFalse(Membership.objects.filter(user=self.existing_user, organization=self.org).exists())

    def test_duplicate_invitation_replaces_existing(self):
        """
        GIVEN an existing invitation for an email
        WHEN a new invitation is sent to the same email
        THEN the old one is replaced
        """
        Invitation.objects.create(
            email='dup@test.com', organization=self.org, role='viewer', invited_by=self.owner,
        )
        self.client.login(username='inv_owner', password='pass')
        self.client.post(f'/org/{self.org.slug}/invite/', {
            'email': 'dup@test.com',
            'role': 'editor',
        })
        invitations = Invitation.objects.filter(email='dup@test.com', organization=self.org)
        self.assertEqual(invitations.count(), 1)
        self.assertEqual(invitations.first().role, 'editor')

    def test_invalid_token_shows_error(self):
        """
        GIVEN a non-existent invitation token
        WHEN a user visits the accept URL
        THEN they are redirected with error
        """
        import uuid
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{uuid.uuid4()}/accept/')
        self.assertEqual(response.status_code, 302)


# ─── Task 6.5: Organization Switcher Tests ──────────────────────────────────

class OrgSwitcherTest(TestCase):
    """Tests for the organization switcher."""

    def setUp(self):
        self.user = User.objects.create_user(username='switcher', password='pass')
        self.org_a = _make_org('OrgA')
        self.org_b = _make_org('OrgB')
        Membership.objects.create(user=self.user, organization=self.org_a, role='owner')
        Membership.objects.create(user=self.user, organization=self.org_b, role='editor')

    def test_switch_org_sets_session(self):
        """
        GIVEN a user with membership in two orgs
        WHEN they POST to switch_org with org_b's id
        THEN the session active_org_id is updated
        """
        self.client.login(username='switcher', password='pass')
        response = self.client.post('/org/switch/', {'org_id': self.org_b.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['active_org_id'], self.org_b.id)

    def test_switch_to_invalid_org_ignored(self):
        """
        GIVEN a user
        WHEN they try to switch to an org they're not a member of
        THEN the switch is silently ignored
        """
        other_org = _make_org('OtherOrg')
        self.client.login(username='switcher', password='pass')
        # First ensure there is an active org
        self.client.post('/org/switch/', {'org_id': self.org_a.id})
        old_org_id = self.client.session['active_org_id']
        self.client.post('/org/switch/', {'org_id': other_org.id})
        # Should stay the same (or fall back)
        self.assertNotEqual(self.client.session.get('active_org_id'), other_org.id)

    def test_middleware_fallback_on_login(self):
        """
        GIVEN a user with membership in one org
        WHEN they log in without active_org_id in session
        THEN middleware sets active_org to their first org
        """
        solo_user = User.objects.create_user(username='solo', password='pass')
        solo_org = _make_org('SoloOrg')
        Membership.objects.create(user=solo_user, organization=solo_org, role='owner')

        self.client.login(username='solo', password='pass')
        response = self.client.get('/editor/')
        self.assertEqual(self.client.session.get('active_org_id'), solo_org.id)

    def test_switch_org_requires_post(self):
        """
        GIVEN an authenticated user
        WHEN they send GET to switch_org
        THEN it is rejected (405 Method Not Allowed)
        """
        self.client.login(username='switcher', password='pass')
        response = self.client.get('/org/switch/')
        self.assertEqual(response.status_code, 405)

    def test_dashboard_shows_surveys_for_active_org(self):
        """
        GIVEN surveys in org_a and org_b
        WHEN user views editor dashboard with org_a active
        THEN only org_a surveys are shown
        """
        survey_a = SurveyHeader.objects.create(name='survey_a', organization=self.org_a)
        survey_b = SurveyHeader.objects.create(name='survey_b', organization=self.org_b)

        self.client.login(username='switcher', password='pass')
        self.client.post('/org/switch/', {'org_id': self.org_a.id})
        response = self.client.get('/editor/')
        self.assertContains(response, 'survey_a')
        self.assertNotContains(response, 'survey_b')


# ─── Task 7.9: Editor View Permission Tests ─────────────────────────────────

class EditorPermissionTest(TestCase):
    """Tests for permission checks on all editor view actions."""

    def setUp(self):
        self.org = _make_org('EditorPermOrg')
        self.owner = User.objects.create_user(username='ep_owner', password='pass')
        self.editor = User.objects.create_user(username='ep_editor', password='pass')
        self.viewer = User.objects.create_user(username='ep_viewer', password='pass')
        self.outsider = User.objects.create_user(username='ep_outsider', password='pass')

        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(name='ep_survey', organization=self.org, created_by=self.owner)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', name='Test Q', input_type='text', order_number=1,
        )
        # Give editor explicit collaborator access
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')

    def test_viewer_cannot_create_survey(self):
        """
        GIVEN an org viewer
        WHEN they try to create a survey
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post('/editor/surveys/new/', {
            'name': 'forbidden_survey', 'redirect_url': '#', 'visibility': 'private',
        })
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_survey(self):
        """
        GIVEN an org editor
        WHEN they create a survey
        THEN it succeeds and is assigned to the active org
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.post('/editor/surveys/new/', {
            'name': 'editor_survey', 'redirect_url': '#', 'visibility': 'private',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='editor_survey')
        self.assertEqual(survey.organization, self.org)
        self.assertEqual(survey.created_by, self.editor)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_viewer_sees_read_only_badge(self):
        """
        GIVEN an org viewer and a published survey
        WHEN they view the survey detail page
        THEN they see the read-only badge
        """
        self.survey.status = 'published'
        self.survey.save()
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'read-only')

    def test_viewer_cannot_create_section(self):
        """
        GIVEN an org viewer
        WHEN they try to create a section
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/new/')
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_section(self):
        """
        GIVEN an org editor with survey collaborator role
        WHEN they create a section
        THEN it succeeds
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/new/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SurveySection.objects.filter(survey_header=self.survey).count(), 2)

    def test_viewer_cannot_delete_question(self):
        """
        GIVEN an org viewer
        WHEN they try to delete a question
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/delete/')
        self.assertEqual(response.status_code, 403)

    def test_editor_can_delete_question(self):
        """
        GIVEN an org editor with survey collaborator role
        WHEN they delete a question
        THEN it succeeds
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/delete/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(id=self.question.id).exists())

    def test_viewer_cannot_reorder_sections(self):
        """
        GIVEN an org viewer
        WHEN they try to reorder sections
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/reorder/',
            json.dumps({'section_ids': [self.section.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_outsider_gets_404_on_survey_detail(self):
        """
        GIVEN a user not in the org
        WHEN they try to view a survey in that org
        THEN they get 404
        """
        other_org = _make_org('OutsiderOrg')
        Membership.objects.create(user=self.outsider, organization=other_org, role='owner')
        self.client.login(username='ep_outsider', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 404)

    def test_editor_without_collab_cannot_edit_others_survey(self):
        """
        GIVEN an org editor with no collaborator entry for a survey
        WHEN they try to access that survey
        THEN they get 403 (editor baseline is None without collab)
        """
        other_survey = SurveyHeader.objects.create(name='other_survey', organization=self.org, created_by=self.owner)
        SurveySection.objects.create(
            survey_header=other_survey, name='osec', code='OS', is_head=True,
        )
        self.client.login(username='ep_editor', password='pass')
        response = self.client.get(f'/editor/surveys/{other_survey.uuid}/')
        self.assertEqual(response.status_code, 403)

    def test_editor_cannot_access_settings(self):
        """
        GIVEN an org editor with 'editor' collaborator role
        WHEN they try to access survey settings
        THEN they get 403 (settings require 'owner')
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings/')
        self.assertEqual(response.status_code, 403)

    def test_owner_can_access_settings(self):
        """
        GIVEN an org owner
        WHEN they access survey settings
        THEN they get 200
        """
        self.client.login(username='ep_owner', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings/')
        self.assertEqual(response.status_code, 200)

    def test_editor_cannot_access_settings_panel(self):
        """
        GIVEN an org editor with 'editor' collaborator role
        WHEN they try to access the pinned settings panel partial
        THEN they get 403 (same 'owner' requirement as the standalone page)
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings-panel/')
        self.assertEqual(response.status_code, 403)

    def test_owner_can_access_settings_panel(self):
        """
        GIVEN an org owner
        WHEN they GET the settings panel partial
        THEN they get 200 with the General settings form and no full page chrome
        """
        self.client.login(username='ep_owner', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings-panel/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('surveySettingsGeneralForm', content)
        self.assertNotIn('<html', content)

    def test_settings_panel_autosave_ajax_returns_json(self):
        """
        GIVEN the settings panel form is submitted via XHR (autosave)
        WHEN the request carries X-Requested-With
        THEN a JSON ok response is returned (no redirect) and the field persists
        """
        self.client.login(username='ep_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/settings-panel/'
        response = self.client.post(
            url,
            {
                'name': self.survey.name,
                'redirect_url': '#',
                'available_languages': '[]',
                'visibility': 'public',
                'thanks_html': '{}',
                'basemaps': '["streets"]',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.visibility, 'public')

    def test_settings_panel_autosave_saves_added_language(self):
        """
        GIVEN an English survey and the settings panel autosave
        WHEN it posts available_languages ["en", "es"]
        THEN the survey keeps both languages (#391)
        """
        self.client.login(username='ep_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/settings-panel/'
        response = self.client.post(url, {
            'name': self.survey.name,
            'redirect_url': '#',
            'available_languages': '["en", "es"]',
            'visibility': 'private',
            'basemaps': '["streets"]',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.available_languages, ['en', 'es'])

    def test_settings_panel_language_picker_triggers_autosave(self):
        """
        GIVEN the settings panel, whose autosave listens for field events only
        WHEN it renders
        THEN the language picker fires change on the hidden input after a
             creator's add/remove, and its search box is excluded from autosave
             (its blur used to save the old languages, #391)
        """
        self.client.login(username='ep_owner', password='pass')
        content = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/settings-panel/').content.decode()
        self.assertIn("hiddenInput.dispatchEvent(new Event('change'", content)
        self.assertRegex(content, r"exclude: '[^']*#lang-search")
        # The initial render syncs without the event, so opening the panel
        # does not save it.
        self.assertIn('renderTags();\n    sync();', content)

    def test_settings_panel_plain_post_redirects(self):
        """
        GIVEN the settings panel form is submitted as a plain (non-XHR) POST
        WHEN the form is valid
        THEN the response redirects back into the editor with the panel selected
        """
        self.client.login(username='ep_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/settings-panel/'
        response = self.client.post(url, {
            'name': self.survey.name,
            'redirect_url': '#',
            'available_languages': '[]',
            'visibility': 'private',
            'thanks_html': '{}',
            'basemaps': '["streets"]',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('panel=settings', response.url)

    def test_survey_detail_with_panel_settings_query_param(self):
        """
        GIVEN the owner loads the editor with ?panel=settings
        WHEN the page renders
        THEN the settings panel is the initial center-panel content and the
             pinned entry is marked active (no section is current)
        """
        self.client.login(username='ep_owner', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/?panel=settings')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('settings-panel/', content)
        self.assertIn('sidebar-pinned-item active', content)

    # ── Lifecycle-IA navigation (Survey / Responses / Public results) ──

    def test_nav_shows_three_lifecycle_spaces(self):
        """
        GIVEN the survey editor
        WHEN it renders for an owner
        THEN the navbar shows Survey/Responses/Public results tabs and no
        Editor/Settings tab
        """
        self.client.login(username='ep_owner', password='pass')
        content = self.client.get(f'/editor/surveys/{self.survey.uuid}/').content.decode()
        self.assertIn('fa-hammer"></i> Survey', content)
        self.assertIn('fa-chart-bar"></i> Responses', content)
        self.assertIn('fa-globe"></i> Public results', content)
        # The old Editor label and the deprecated Settings tab are gone
        self.assertNotIn('title="Editor"', content)
        self.assertNotIn('badge-moved', content)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_publishing_widget_renders_on_all_spaces(self):
        """
        GIVEN an owner
        WHEN they open Build, Results, and Publish
        THEN the publishing widget (status chip) renders on each
        """
        self.client.login(username='ep_owner', password='pass')
        for path in ('', 'analytics/', 'public-results/'):
            content = self.client.get(f'/editor/surveys/{self.survey.uuid}/{path}').content.decode()
            self.assertIn('publishing-widget', content, msg=f'missing on /{path}')

    def test_draft_survey_shows_prominent_publish_and_discard(self):
        """
        GIVEN a canonical draft survey
        WHEN the owner opens Build
        THEN prominent Publish (draft→published) and Discard (delete draft)
             actions are present; a published survey shows neither
        """
        self.client.login(username='ep_owner', password='pass')
        content = self.client.get(f'/editor/surveys/{self.survey.uuid}/').content.decode()
        self.assertIn("doTransition('published')", content)
        self.assertIn('discardDraftSurveyModal', content)
        # Once published, the prominent draft actions disappear
        self.survey.status = 'published'
        self.survey.save()
        content = self.client.get(f'/editor/surveys/{self.survey.uuid}/').content.decode()
        self.assertNotIn('discardDraftSurveyModal', content)

    def test_visibility_toggle_owner(self):
        """
        GIVEN an owner
        WHEN they POST a new visibility via the widget endpoint
        THEN only the visibility field changes and JSON is returned for XHR
        """
        self.client.login(username='ep_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/visibility/'
        r = self.client.post(url, {'visibility': 'public'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['visibility'], 'public')
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.visibility, 'public')
        # invalid value rejected
        r = self.client.post(url, {'visibility': 'bogus'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 400)

    def test_visibility_toggle_non_owner_blocked(self):
        """
        GIVEN an org editor (not owner)
        WHEN they try to toggle visibility
        THEN they get 403
        """
        self.client.login(username='ep_editor', password='pass')
        r = self.client.post(f'/editor/surveys/{self.survey.uuid}/visibility/', {'visibility': 'public'})
        self.assertEqual(r.status_code, 403)


# ─── Task 8.4: Export/Import/Delete Permission Tests ────────────────────────

class ExportImportDeletePermissionTest(TestCase):
    """Tests for export, import, and delete permission checks."""

    def setUp(self):
        self.org = _make_org('EIDOrg')
        self.owner = User.objects.create_user(username='eid_owner', password='pass')
        self.editor = User.objects.create_user(username='eid_editor', password='pass')
        self.viewer = User.objects.create_user(username='eid_viewer', password='pass')

        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(name='eid_survey', organization=self.org)
        SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )

    def test_viewer_can_export(self):
        """
        GIVEN an org viewer
        WHEN they export a survey
        THEN the export succeeds (viewers have read access)
        """
        self.client.login(username='eid_viewer', password='pass')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=structure')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_viewer_cannot_import(self):
        """
        GIVEN an org viewer
        WHEN they try to import a survey
        THEN they get 403
        """
        self.client.login(username='eid_viewer', password='pass')
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps({
                'version': '1.0',
                'survey': {'name': 'forbidden', 'sections': [{'name': 's', 'code': 'S', 'is_head': True, 'questions': []}]},
            }))
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('test.zip', buf.read(), content_type='application/zip')
        with _eager_import():
            response = self.client.post('/editor/import/', {'file': f})
        self.assertEqual(response.status_code, 403)

    def test_editor_can_import(self):
        """
        GIVEN an org editor
        WHEN they import a survey
        THEN it succeeds and the survey is assigned to the active org
        """
        self.client.login(username='eid_editor', password='pass')
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps({
                'version': '1.0',
                'survey': {'name': 'imported_survey', 'sections': [{'name': 's', 'code': 'S', 'is_head': True, 'questions': []}]},
            }))
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('test.zip', buf.read(), content_type='application/zip')
        with _eager_import():
            response = self.client.post('/editor/import/', {'file': f})
        self.assertEqual(response.status_code, 302)
        imported = SurveyHeader.objects.get(name='imported_survey')
        self.assertEqual(imported.organization, self.org)

    def test_viewer_cannot_delete(self):
        """
        GIVEN an org viewer
        WHEN they try to delete a survey
        THEN they get 403
        """
        self.client.login(username='eid_viewer', password='pass')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.survey.pk).exists())

    def test_editor_cannot_delete(self):
        """
        GIVEN an org editor (even with survey collaborator editor role)
        WHEN they try to delete a survey
        THEN they get 403 (delete requires owner)
        """
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.client.login(username='eid_editor', password='pass')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.survey.pk).exists())

    def test_owner_can_delete(self):
        """
        GIVEN an org owner
        WHEN they delete a survey
        THEN it is moved to trash
        """
        self.client.login(username='eid_owner', password='pass')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertIsNotNone(self.survey.deleted_at)

    def test_export_survey_in_different_org_returns_404(self):
        """
        GIVEN a survey in org_a
        WHEN a user with active_org=org_b tries to export it
        THEN they get 404
        """
        org_b = _make_org('OtherEIDOrg')
        other_user = User.objects.create_user(username='eid_other', password='pass')
        Membership.objects.create(user=other_user, organization=org_b, role='owner')
        self.client.login(username='eid_other', password='pass')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=structure')
        self.assertEqual(response.status_code, 404)


# ─── Task 9.7: Collaborator Management Tests ────────────────────────────────

class CollaboratorManagementTest(TestCase):
    """Tests for add/change/remove collaborators and last-owner protection."""

    def setUp(self):
        self.org = _make_org('CollabOrg')
        self.owner = User.objects.create_user(username='coll_owner', password='pass')
        self.member = User.objects.create_user(username='coll_member', password='pass')
        self.editor = User.objects.create_user(username='coll_editor', password='pass')

        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.member, organization=self.org, role='viewer')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')

        self.survey = SurveyHeader.objects.create(name='collab_survey', organization=self.org, created_by=self.owner)
        SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')

    def test_owner_can_add_collaborator(self):
        """
        GIVEN a survey owner
        WHEN they add an org member as a collaborator
        THEN the collaborator record is created
        """
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/collaborators/add/', {
            'user_id': self.member.id,
            'role': 'editor',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SurveyCollaborator.objects.filter(
            user=self.member, survey=self.survey, role='editor',
        ).exists())

    def test_non_owner_cannot_add_collaborator(self):
        """
        GIVEN an org editor with survey editor role
        WHEN they try to add a collaborator
        THEN they get 403
        """
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.client.login(username='coll_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/collaborators/add/', {
            'user_id': self.member.id,
            'role': 'viewer',
        })
        self.assertEqual(response.status_code, 403)

    def test_change_collaborator_role(self):
        """
        GIVEN a survey owner and an existing collaborator
        WHEN they change the collaborator's role
        THEN the role is updated
        """
        collab = SurveyCollaborator.objects.create(user=self.member, survey=self.survey, role='viewer')
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{collab.id}/role/',
            {'role': 'editor'},
        )
        self.assertEqual(response.status_code, 200)
        collab.refresh_from_db()
        self.assertEqual(collab.role, 'editor')

    def test_remove_collaborator(self):
        """
        GIVEN a survey owner and a collaborator
        WHEN they remove the collaborator
        THEN the collaborator record is deleted
        """
        collab = SurveyCollaborator.objects.create(user=self.member, survey=self.survey, role='viewer')
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{collab.id}/remove/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SurveyCollaborator.objects.filter(user=self.member, survey=self.survey).exists())

    def test_cannot_remove_last_survey_owner(self):
        """
        GIVEN a survey with only one owner collaborator
        WHEN they try to remove that owner
        THEN they get 400 error
        """
        self.client.login(username='coll_owner', password='pass')
        owner_collab = SurveyCollaborator.objects.get(user=self.owner, survey=self.survey)
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{owner_collab.id}/remove/',
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(SurveyCollaborator.objects.filter(user=self.owner, survey=self.survey).exists())

    def test_can_remove_owner_when_multiple_owners_exist(self):
        """
        GIVEN a survey with two owner collaborators
        WHEN one owner removes the other
        THEN the removal succeeds
        """
        SurveyCollaborator.objects.create(user=self.member, survey=self.survey, role='owner')
        self.client.login(username='coll_owner', password='pass')
        member_collab = SurveyCollaborator.objects.get(user=self.member, survey=self.survey)
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{member_collab.id}/remove/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SurveyCollaborator.objects.filter(user=self.member, survey=self.survey).exists())

    def test_add_non_org_member_rejected(self):
        """
        GIVEN a user not in the org
        WHEN survey owner tries to add them as collaborator
        THEN it is rejected with 400
        """
        outsider = User.objects.create_user(username='coll_outsider', password='pass')
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/collaborators/add/', {
            'user_id': outsider.id,
            'role': 'viewer',
        })
        self.assertEqual(response.status_code, 400)


# ─── Task 11.3: CLI Import with Organization Tests ──────────────────────────

class CLIImportWithOrgTest(TestCase):
    """Tests for the import_survey management command with --organization."""

    def setUp(self):
        self.org = _make_org('CLIOrg')
        self.other_org = _make_org('OtherCLIOrg')
        self.survey_data = {
            'version': '1.0',
            'survey': {
                'name': 'cli_import_test',
                'sections': [{
                    'name': 'sec1', 'code': 'S1', 'is_head': True, 'questions': [],
                }],
            },
        }

    def _create_zip(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps(self.survey_data))
        buf.seek(0)
        return buf

    def test_import_with_org_name(self):
        """
        GIVEN a ZIP archive and an existing organization
        WHEN import_survey is called with --organization=<name>
        THEN the survey is assigned to that organization
        """
        from django.core.management import call_command
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                call_command('import_survey', f.name, organization='CLIOrg', stdout=StringIO())
                survey = SurveyHeader.objects.get(name='cli_import_test')
                self.assertEqual(survey.organization, self.org)
            finally:
                os.unlink(f.name)

    def test_import_with_org_slug(self):
        """
        GIVEN a ZIP archive and an existing organization
        WHEN import_survey is called with --organization=<slug>
        THEN the survey is assigned to that organization
        """
        from django.core.management import call_command
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                call_command('import_survey', f.name, organization=self.other_org.slug, stdout=StringIO())
                survey = SurveyHeader.objects.get(name='cli_import_test')
                self.assertEqual(survey.organization, self.other_org)
            finally:
                os.unlink(f.name)

    def test_import_with_unknown_org_raises_error(self):
        """
        GIVEN a ZIP archive
        WHEN import_survey is called with --organization=<nonexistent>
        THEN it raises CommandError
        """
        from django.core.management import call_command, CommandError
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                with self.assertRaises(CommandError):
                    call_command('import_survey', f.name, organization='nonexistent', stderr=StringIO())
            finally:
                os.unlink(f.name)

    def test_import_without_org_uses_default(self):
        """
        GIVEN a ZIP archive without --organization
        WHEN import_survey is called
        THEN the survey is assigned based on archive data or default
        """
        from django.core.management import call_command
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                call_command('import_survey', f.name, stdout=StringIO())
                survey = SurveyHeader.objects.get(name='cli_import_test')
                self.assertIsNotNone(survey.organization)
            finally:
                os.unlink(f.name)


# ─── Task 3.6: Registration and Personal Org Creation Tests ─────────────────

class PersonalOrgCreationTest(TestCase):
    """Tests for personal org creation on user registration signal."""

    def test_signal_creates_personal_org(self):
        """
        GIVEN a newly registered user
        WHEN the user_registered signal fires
        THEN a personal org is created and user is set as owner
        """
        from django_registration.signals import user_registered
        from django.test import RequestFactory
        user = User.objects.create_user(username='newuser', password='pass', email='new@test.com')
        factory = RequestFactory()
        request = factory.get('/')
        # Simulate session
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()

        user_registered.send(sender=self.__class__, user=user, request=request)

        # Personal org should exist
        self.assertTrue(Membership.objects.filter(user=user, role='owner').exists())
        membership = Membership.objects.get(user=user, role='owner')
        self.assertIn(user.username, membership.organization.name)

    def test_signal_auto_accepts_pending_invitations(self):
        """
        GIVEN a pending invitation for a new user's email
        WHEN the user registers
        THEN the invitation is auto-accepted and user joins the org
        """
        from django_registration.signals import user_registered
        from django.test import RequestFactory
        from django.contrib.sessions.backends.db import SessionStore

        invite_org = _make_org('InviteTargetOrg')
        inviter = User.objects.create_user(username='inviter', password='pass')
        Membership.objects.create(user=inviter, organization=invite_org, role='owner')
        invitation = Invitation.objects.create(
            email='newbie@test.com', organization=invite_org, role='editor', invited_by=inviter,
        )

        user = User.objects.create_user(username='newbie', password='pass', email='newbie@test.com')
        factory = RequestFactory()
        request = factory.get('/')
        request.session = SessionStore()

        user_registered.send(sender=self.__class__, user=user, request=request)

        # User should have membership in invite_org
        self.assertTrue(Membership.objects.filter(user=user, organization=invite_org, role='editor').exists())
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)


# ─── Invitation Flow for Unregistered Users ──────────────────────────────────

class InvitationFlowTest(TestCase):
    """Tests for the invitation flow supporting unauthenticated users."""

    def setUp(self):
        self.org = _make_org('FlowOrg')
        self.owner = User.objects.create_user(username='flow_owner', password='pass')
        self.existing_user = User.objects.create_user(username='flow_existing', password='pass', email='flow@test.com')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_invitation(self, **kwargs):
        defaults = dict(
            email='invitee@test.com',
            organization=self.org,
            role='editor',
            invited_by=self.owner,
        )
        defaults.update(kwargs)
        return Invitation.objects.create(**defaults)

    def test_unauthenticated_user_sees_landing_page(self):
        """
        GIVEN a valid pending invitation
        WHEN an unauthenticated user visits the accept URL
        THEN they see the invitation landing page with org details
        """
        invitation = self._make_invitation()
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.org.name)
        self.assertContains(response, 'editor')
        self.assertContains(response, self.owner.username)

    def test_token_stored_in_session(self):
        """
        GIVEN a valid pending invitation
        WHEN an unauthenticated user visits the accept URL
        THEN the invitation token is stored in the session
        """
        invitation = self._make_invitation()
        self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(
            self.client.session.get('pending_invitation_token'),
            str(invitation.token),
        )

    def test_expired_invitation_shows_error(self):
        """
        GIVEN an invitation older than 7 days
        WHEN an unauthenticated user visits the accept URL
        THEN they see an expiry error message
        """
        from django.utils import timezone
        from datetime import timedelta
        invitation = self._make_invitation()
        Invitation.objects.filter(pk=invitation.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expired')
        self.assertNotIn('pending_invitation_token', self.client.session)

    def test_already_accepted_invitation_shows_info(self):
        """
        GIVEN an invitation that has already been accepted
        WHEN an unauthenticated user visits the accept URL
        THEN they see an "already used" message
        """
        from django.utils import timezone
        invitation = self._make_invitation(accepted_at=timezone.now())
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already been used')

    def test_invalid_token_shows_error(self):
        """
        GIVEN a non-existent invitation token
        WHEN an unauthenticated user visits the accept URL
        THEN they see an error message
        """
        import uuid as _uuid
        response = self.client.get(f'/invitations/{_uuid.uuid4()}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid invitation link')

    def test_middleware_processes_pending_token_after_login(self):
        """
        GIVEN a pending invitation token stored in the session
        WHEN the user logs in and the middleware runs
        THEN the invitation is accepted and membership is created
        """
        invitation = self._make_invitation(email='flow@test.com')
        # Visit accept URL as anonymous to store token
        self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(
            self.client.session.get('pending_invitation_token'),
            str(invitation.token),
        )
        # Log in — middleware should pick up the token
        self.client.login(username='flow_existing', password='pass')
        self.client.get('/editor/')
        # Membership should exist
        self.assertTrue(
            Membership.objects.filter(
                user=self.existing_user, organization=self.org, role='editor'
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        # Token should be removed from session
        self.assertNotIn('pending_invitation_token', self.client.session)

    def test_authenticated_user_still_works_directly(self):
        """
        GIVEN an authenticated user and a pending invitation
        WHEN they visit the accept URL directly
        THEN they are added to the org immediately (existing behavior)
        """
        invitation = self._make_invitation(email='flow@test.com')
        self.client.login(username='flow_existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Membership.objects.filter(
                user=self.existing_user, organization=self.org, role='editor'
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)

    def test_middleware_cleans_up_invalid_pending_token(self):
        """
        GIVEN a pending invitation token in session that has become invalid
        WHEN the user logs in and the middleware runs
        THEN the token is silently removed without error
        """
        import uuid as _uuid
        # Give the user an org so /editor/ doesn't 403
        personal_org = _make_org('PersonalOrg')
        Membership.objects.create(user=self.existing_user, organization=personal_org, role='owner')
        # Manually set a bogus token in session
        session = self.client.session
        session['pending_invitation_token'] = str(_uuid.uuid4())
        session.save()
        # Log in and visit a page — should not error
        self.client.login(username='flow_existing', password='pass')
        # ?dashboard=1 keeps this on the dashboard: the org has no surveys, and
        # a bare /editor/ would redirect to the create page, which says nothing
        # about the middleware under test.
        response = self.client.get('/editor/?dashboard=1')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('pending_invitation_token', self.client.session)
