"""Tests for the `workspace-invitation-journey` capability (change invite-landing-journey, #512).

Where a person invited into a workspace ends up: the one acceptance path in
`survey/invitations.py`, the landing page carrying the token into registration
and sign-in, no personal workspace for an invited registration, the dashboard
with the "You've joined" banner instead of the start page, and the editor's
empty state.
"""
import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from survey import invitations
from survey.models import Invitation, Membership, Organization, SurveyHeader
from survey.tests.helpers import _InlineThread, _activation_key, _make_org

PASSWORD = 'Xx12345!secure'
START_URL = '/editor/surveys/start/?welcome=1'


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)  # no registration rate-limit counters left for the next test
        mail.outbox = []
        patcher = mock.patch('threading.Thread', _InlineThread)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.org = _make_org('Team Org')
        self.owner = User.objects.create_user('team_owner', 'owner@example.org', PASSWORD)
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _invite(self, email='newbie@example.org', role='editor', org=None):
        return Invitation.objects.create(
            email=email, organization=org or self.org, role=role, invited_by=self.owner,
        )

    def _survey(self, org=None):
        return SurveyHeader.objects.create(name='Existing', organization=org or self.org, created_by=self.owner)

    def _register(self, username='newbie', email='newbie@example.org'):
        return self.client.post('/accounts/register/', {
            'username': username, 'email': email,
            'password1': PASSWORD, 'password2': PASSWORD,
            'website': '', 'accept_terms': 'on',
        })

    def _accept_url(self, invitation):
        return reverse('accept_invitation', args=[invitation.token])

    def _memberships(self, username):
        return sorted(Membership.objects.filter(user__username=username)
                      .values_list('organization__name', 'role'))

    def _active_org_id(self):
        return self.client.session.get('active_org_id')


class AcceptancePathTest(_Base):
    """One module writes every acceptance."""

    def test_signed_in_visitor_opens_the_link(self):
        """
        GIVEN a signed-in user and an acceptable invitation
        WHEN they open the invitation link
        THEN they are a member with the invited role, the invitation is accepted, the
             workspace is active and the response redirects to the dashboard
        """
        invitation = self._invite(email='someone@example.org')
        user = User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        self.client.login(username='someone', password=PASSWORD)

        response = self.client.get(self._accept_url(invitation))

        self.assertRedirects(response, '/editor/', fetch_redirect_response=False)
        self.assertTrue(Membership.objects.filter(user=user, organization=self.org, role='editor').exists())
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        self.assertEqual(self._active_org_id(), self.org.id)

    def test_parked_token_is_accepted_on_the_first_signed_in_request(self):
        """
        GIVEN a signed-out visitor who opened the link (token parked) and then signs in
        WHEN they make any request
        THEN the invitation is accepted, the workspace is active and the token is gone
        """
        invitation = self._invite(email='someone@example.org')
        User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        self.client.get(self._accept_url(invitation))
        self.assertEqual(self.client.session.get(invitations.SESSION_TOKEN_KEY), str(invitation.token))

        self.client.login(username='someone', password=PASSWORD)
        self.client.get('/editor/account/')

        self.assertTrue(Membership.objects.filter(user__username='someone', organization=self.org).exists())
        self.assertEqual(self._active_org_id(), self.org.id)
        self.assertNotIn(invitations.SESSION_TOKEN_KEY, self.client.session)

    def test_dead_token_is_dropped(self):
        """
        GIVEN a parked token that names a used invitation
        WHEN the signed-in user makes a request
        THEN nothing is written and the token leaves the session
        """
        from django.utils import timezone
        invitation = self._invite(email='someone@example.org')
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])
        User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        session = self.client.session
        session[invitations.SESSION_TOKEN_KEY] = str(invitation.token)
        session.save()

        self.client.login(username='someone', password=PASSWORD)
        self.client.get('/editor/account/')

        self.assertFalse(Membership.objects.filter(user__username='someone').exists())
        self.assertNotIn(invitations.SESSION_TOKEN_KEY, self.client.session)

    def test_existing_member_keeps_their_role(self):
        """
        GIVEN an admin of the workspace who is sent a viewer invitation
        WHEN they accept it
        THEN their membership stays admin
        """
        admin = User.objects.create_user('admin_one', 'admin@example.org', PASSWORD)
        Membership.objects.create(user=admin, organization=self.org, role='admin')
        invitation = self._invite(email='admin@example.org', role='viewer')
        self.client.login(username='admin_one', password=PASSWORD)

        self.client.get(self._accept_url(invitation))

        self.assertEqual(Membership.objects.get(user=admin, organization=self.org).role, 'admin')

    def test_acceptance_is_measured(self):
        """
        GIVEN an invitation accepted through the link
        WHEN the event is emitted
        THEN it carries the organisation id, the role and the surface, and nothing else
        """
        invitation = self._invite(email='someone@example.org')
        user = User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        self.client.login(username='someone', password=PASSWORD)

        with mock.patch('survey.invitations.pe.emit') as emit:
            self.client.get(self._accept_url(invitation))

        emit.assert_called_once_with('invitation_accepted', user.pk, {
            'organization_id': self.org.id, 'role': 'editor', 'surface': 'link',
        })


class LandingPageTest(_Base):
    """The landing page carries the token into both doors."""

    def test_landing_links(self):
        """
        GIVEN an acceptable invitation
        WHEN a signed-out visitor opens the link
        THEN the page names inviter, workspace and role, and its actions carry the token
        """
        invitation = self._invite()
        response = self.client.get(self._accept_url(invitation))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Team Org')
        self.assertContains(response, 'team_owner')
        self.assertContains(response, 'editor')
        self.assertContains(response, f'/accounts/register/?invite={invitation.token}')
        accept_path = self._accept_url(invitation).replace('/', '%2F')
        self.assertContains(response, f'/accounts/login/?next={accept_path}')
        self.assertEqual(self.client.session.get(invitations.SESSION_TOKEN_KEY), str(invitation.token))

    def test_registration_page_from_the_landing(self):
        """
        GIVEN the registration page opened with the invitation's parameter in a fresh session
        WHEN it renders
        THEN the email field holds the invited address, the page names the workspace and the
             token is parked
        """
        invitation = self._invite()
        response = self.client.get(f'/accounts/register/?invite={invitation.token}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="newbie@example.org"')
        self.assertContains(response, 'Create an account to join Team Org.')
        self.assertEqual(self.client.session.get(invitations.SESSION_TOKEN_KEY), str(invitation.token))

    def test_expired_invite_parameter_is_ignored(self):
        """
        GIVEN an expired invitation
        WHEN the registration page is opened with its parameter
        THEN the page is plain registration and nothing is parked
        """
        from datetime import timedelta
        from django.utils import timezone
        invitation = self._invite()
        Invitation.objects.filter(pk=invitation.pk).update(created_at=timezone.now() - timedelta(days=8))

        response = self.client.get(f'/accounts/register/?invite={invitation.token}')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Create an account to join')
        self.assertContains(response, 'Sign up to create and manage geo-surveys.')
        self.assertNotIn(invitations.SESSION_TOKEN_KEY, self.client.session)

    def test_garbage_invite_parameter_is_ignored(self):
        """
        GIVEN a value that is not a UUID
        WHEN the registration page is opened with it
        THEN the page renders as plain registration
        """
        response = self.client.get('/accounts/register/?invite=not-a-token')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(invitations.SESSION_TOKEN_KEY, self.client.session)

    def test_sign_in_through_the_landing_lands_on_the_dashboard(self):
        """
        GIVEN an existing account that opened the landing page
        WHEN it signs in through the landing's sign-in link (next = the accept URL)
        THEN the accept URL joins the workspace and redirects to the dashboard, which
             shows the joined banner
        """
        invitation = self._invite(email='someone@example.org')
        User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        self._survey()
        self.client.get(self._accept_url(invitation))

        response = self.client.post(
            f"{reverse('login')}?next={self._accept_url(invitation)}",
            {'username': 'someone', 'password': PASSWORD},
        )
        self.assertRedirects(response, self._accept_url(invitation), fetch_redirect_response=False)
        response = self.client.get(self._accept_url(invitation))
        self.assertRedirects(response, '/editor/', fetch_redirect_response=False)
        response = self.client.get('/editor/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="joined-banner"')
        self.assertEqual(self._active_org_id(), self.org.id)


class InvitedRegistrationTest(_Base):
    """A registration that carries an invitation joins the workspace and creates no personal one."""

    def test_register_through_the_link(self):
        """
        GIVEN a signed-out visitor who opened an acceptable invitation link
        WHEN they follow Create account and register
        THEN the account's only membership is the inviting workspace, with the invited role,
             no organisation is named after the account, the workspace is active and
             /editor/ renders its dashboard with the banner
        """
        invitation = self._invite()
        self.client.get(self._accept_url(invitation))
        self.client.get(f'/accounts/register/?invite={invitation.token}')

        response = self._register()

        self.assertRedirects(response, '/editor/', fetch_redirect_response=False)
        self.assertEqual(self._memberships('newbie'), [('Team Org', 'editor')])
        self.assertFalse(Organization.objects.filter(name__icontains='newbie').exists())
        self.assertEqual(self._active_org_id(), self.org.id)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)

        response = self.client.get('/editor/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="joined-banner"')
        self.assertContains(response, 'Team Org')

    def test_invitation_died_between_landing_and_submit(self):
        """
        GIVEN a visitor who opened the link, after which the invitation was used by someone else
        WHEN they register
        THEN registration creates the personal workspace and joins nothing
        """
        from django.utils import timezone
        invitation = self._invite()
        self.client.get(self._accept_url(invitation))
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])

        response = self._register()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._memberships('newbie'), [("newbie's workspace", 'owner')])
        self.assertNotIn(invitations.SESSION_TOKEN_KEY, self.client.session)

    def test_different_address_on_the_form(self):
        """
        GIVEN an invitation to a@example.org parked in the session
        WHEN the form is submitted with b@example.org
        THEN the account still joins through the token and no personal workspace is created
        """
        invitation = self._invite(email='a@example.org')
        self.client.get(self._accept_url(invitation))

        self._register(username='bee', email='b@example.org')

        self.assertEqual(self._memberships('bee'), [('Team Org', 'editor')])
        self.assertFalse(Organization.objects.filter(name__icontains='bee').exists())

    def test_registration_without_an_invitation_keeps_the_personal_workspace(self):
        """
        GIVEN no invitation in the session
        WHEN someone registers
        THEN the personal workspace is created as before and /editor/ goes to the start page
        """
        self._register()

        self.assertEqual(self._memberships('newbie'), [("newbie's workspace", 'owner')])
        response = self.client.get('/editor/')
        self.assertRedirects(response, START_URL, fetch_redirect_response=False)

    def test_registration_surface_is_measured(self):
        """
        GIVEN an invitation parked in the session
        WHEN the registration accepts it
        THEN one invitation_accepted event with surface=register is emitted
        """
        invitation = self._invite()
        self.client.get(self._accept_url(invitation))

        with mock.patch('survey.invitations.pe.emit') as emit:
            self._register()

        surfaces = [c.args[2]['surface'] for c in emit.call_args_list if c.args[0] == 'invitation_accepted']
        self.assertEqual(surfaces, ['register'])


class LandingOnTheDashboardTest(_Base):
    """The invitee lands on the workspace dashboard with a joined banner, once."""

    def test_banner_once_then_the_ordinary_rule(self):
        """
        GIVEN an invitee whose acceptance just marked the session, in a workspace with no surveys
        WHEN they open /editor/ twice
        THEN the first response is the dashboard with the banner, the second redirects to the
             start page
        """
        invitation = self._invite(email='someone@example.org')
        User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        self.client.login(username='someone', password=PASSWORD)
        self.client.get(self._accept_url(invitation))

        first = self.client.get('/editor/')
        self.assertEqual(first.status_code, 200)
        self.assertContains(first, 'id="joined-banner"')
        self.assertContains(first, 'Team Org')
        self.assertContains(first, 'Surveys you create here, and the ones a colleague adds you to')
        self.assertNotIn(invitations.JOINED_KEY, self.client.session)

        second = self.client.get('/editor/')
        self.assertRedirects(second, START_URL, fetch_redirect_response=False)

    def test_banner_names_the_active_workspace_only(self):
        """
        GIVEN a session carrying the joined mark for one workspace while another is active
        WHEN the dashboard renders
        THEN no banner renders and the mark is cleared
        """
        other = _make_org('Other Org')
        user = User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        Membership.objects.create(user=user, organization=other, role='owner')
        Membership.objects.create(user=user, organization=self.org, role='editor')
        self._survey(other)
        self.client.login(username='someone', password=PASSWORD)
        session = self.client.session
        session['active_org_id'] = other.id
        session[invitations.JOINED_KEY] = self.org.id
        session.save()

        response = self.client.get('/editor/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="joined-banner"')
        self.assertNotIn(invitations.JOINED_KEY, self.client.session)

    def test_owner_banner_has_no_editor_sentence(self):
        """
        GIVEN an invitee with the admin role
        WHEN the banner renders
        THEN it names the workspace without the editor's explanation
        """
        invitation = self._invite(email='someone@example.org', role='admin')
        User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        self.client.login(username='someone', password=PASSWORD)
        self.client.get(self._accept_url(invitation))

        response = self.client.get('/editor/')

        self.assertContains(response, 'id="joined-banner"')
        self.assertNotContains(response, 'Surveys you create here, and the ones a colleague adds you to')

    def test_confirmation_lands_in_the_joined_workspace(self):
        """
        GIVEN an account registered directly with an invited address (no token), which got a
              personal workspace and no membership yet
        WHEN it confirms the address
        THEN the redirect reaches /editor/ with the inviting workspace active and the banner,
             and the personal workspace remains a second membership
        """
        self._invite()
        self._register()
        self.assertEqual(self._memberships('newbie'), [("newbie's workspace", 'owner')])

        response = self.client.post('/accounts/activate/', {'activation_key': _activation_key('newbie')})

        self.assertRedirects(response, '/editor/', fetch_redirect_response=False)
        self.assertEqual(self._memberships('newbie'), [('Team Org', 'editor'), ("newbie's workspace", 'owner')])
        self.assertEqual(self._active_org_id(), self.org.id)
        response = self.client.get('/editor/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="joined-banner"')
        self.assertContains(response, 'Team Org')

    def test_confirmation_without_an_invitation_is_unchanged(self):
        """
        GIVEN an account with no invitation
        WHEN it confirms the address
        THEN it is signed in and sent to /editor/, which goes to the start page as before
        """
        self._register()
        response = self.client.post('/accounts/activate/', {'activation_key': _activation_key('newbie')})
        self.assertRedirects(response, '/editor/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newbie').pk)
        self.assertRedirects(self.client.get('/editor/'), START_URL, fetch_redirect_response=False)

    def test_confirmation_survives_another_account_in_the_browser(self):
        """
        GIVEN the browser is signed in as a different account
        WHEN the invitee confirms their address from the activation link
        THEN the invitee is signed in, the inviting workspace is active and the banner shows
             (sign-in runs before the receivers, so the flushed session is not the one written)
        """
        self._invite()
        self._register()
        self.client.logout()
        self.client.login(username='team_owner', password=PASSWORD)

        response = self.client.post('/accounts/activate/', {'activation_key': _activation_key('newbie')})

        self.assertRedirects(response, '/editor/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), User.objects.get(username='newbie').pk)
        self.assertEqual(self._active_org_id(), self.org.id)
        self.assertContains(self.client.get('/editor/'), 'id="joined-banner"')


class EditorEmptyStateTest(_Base):
    """An editor who sees none of the surveys reads why."""

    def test_editor_in_a_populated_workspace(self):
        """
        GIVEN an editor with no own or collaborated survey in a workspace that has surveys
        WHEN they open the dashboard
        THEN the empty state names the workspace and explains what appears here
        """
        self._survey()
        user = User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        Membership.objects.create(user=user, organization=self.org, role='editor')
        self.client.login(username='someone', password=PASSWORD)

        response = self.client.get('/editor/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No surveys of yours in Team Org yet.')
        self.assertNotContains(response, 'No surveys yet. Create your first one!')

    def test_owner_of_an_empty_workspace(self):
        """
        GIVEN an owner whose workspace has no surveys
        WHEN they open /editor/?dashboard=1
        THEN the default empty state renders
        """
        self.client.login(username='team_owner', password=PASSWORD)
        response = self.client.get('/editor/?dashboard=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No surveys yet. Create your first one!')
        self.assertNotContains(response, 'No surveys of yours')

    def test_editor_with_a_survey_sees_the_list(self):
        """
        GIVEN an editor who created a survey in the workspace
        WHEN they open the dashboard
        THEN the survey is listed and no empty state renders
        """
        user = User.objects.create_user('someone', 'someone@example.org', PASSWORD)
        Membership.objects.create(user=user, organization=self.org, role='editor')
        SurveyHeader.objects.create(name='Mine', organization=self.org, created_by=user)
        self.client.login(username='someone', password=PASSWORD)

        response = self.client.get('/editor/')

        self.assertContains(response, 'Mine')
        self.assertNotContains(response, 'No surveys of yours')


class PendingHelperTest(TestCase):
    """`acceptable` tolerates whatever the query string carries."""

    def test_acceptable_rejects_non_uuids_and_unknown_tokens(self):
        """
        GIVEN garbage, None and an unknown UUID
        WHEN acceptable() is asked
        THEN it answers None for each without raising
        """
        self.assertIsNone(invitations.acceptable(None))
        self.assertIsNone(invitations.acceptable(''))
        self.assertIsNone(invitations.acceptable('not-a-token'))
        self.assertIsNone(invitations.acceptable(str(uuid.uuid4())))
