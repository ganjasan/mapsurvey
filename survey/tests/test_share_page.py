"""Tests for the `share-page` capability (openspec/specs/share-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, Membership, SurveyCollaborator
from survey.models import TrackedLink
from survey.tests.helpers import _make_org


class ShareViewTest(TestCase):
    """Tests for the Share page view."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('ShareOrg')
        self.user = User.objects.create_user('shareuser', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='sharesurvey', organization=self.org, created_by=self.user,
        )
        self.client.login(username='shareuser', password='pw')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_share_page_get_returns_200(self):
        """
        GIVEN an authenticated editor user
        WHEN the share page is requested via GET
        THEN the response is 200
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/share/')
        self.assertEqual(response.status_code, 200)

    def test_share_page_post_creates_link(self):
        """
        GIVEN an authenticated editor user
        WHEN a POST with utm_source is submitted
        THEN a TrackedLink is created and user is redirected
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/share/',
            {'utm_source': 'newsletter', 'utm_medium': 'email', 'utm_campaign': ''},
        )
        self.assertEqual(TrackedLink.objects.filter(survey=self.survey).count(), 1)
        self.assertRedirects(response, f'/editor/surveys/{self.survey.uuid}/share/')

    def test_share_page_post_missing_source(self):
        """
        GIVEN an authenticated editor user
        WHEN a POST with empty utm_source is submitted
        THEN no TrackedLink is created
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/share/',
            {'utm_source': '', 'utm_medium': '', 'utm_campaign': ''},
        )
        self.assertEqual(TrackedLink.objects.filter(survey=self.survey).count(), 0)

    def test_share_link_delete(self):
        """
        GIVEN a TrackedLink exists
        WHEN DELETE POST is sent
        THEN the link is removed
        """
        link = TrackedLink.objects.create(survey=self.survey, utm_source='test')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/share/{link.id}/delete/',
        )
        self.assertFalse(TrackedLink.objects.filter(id=link.id).exists())


class SharePublishGateTest(TestCase):
    """The Share page gates public links behind publish state (backlog task 85)."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('GateOrg')
        self.owner = User.objects.create_user('gate_owner', password='pw')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='gatesurvey', organization=self.org, created_by=self.owner, status='draft',
        )
        # publishable structure: a head section with a question
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, name='Q1', input_type='text', order_number=1,
        )

    def _login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _share_html(self, survey=None):
        survey = survey or self.survey
        return self.client.get(f'/editor/surveys/{survey.uuid}/share/').content.decode()

    def test_draft_hides_links_and_shows_publish(self):
        """
        GIVEN a draft survey with publishable structure
        WHEN its owner opens Share
        THEN the copyable links are hidden and an inline Publish control is shown
        """
        self._login(self.owner)
        html = self._share_html()
        self.assertIn('still a Draft', html)
        self.assertIn('publishFromShare(this)', html)   # inline gate button (not the header widget)
        self.assertNotIn('id="direct-link"', html)

    def test_published_shows_links_no_banner(self):
        """
        GIVEN a published survey
        WHEN its owner opens Share
        THEN the shareable links render and no publish banner is shown
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        self._login(self.owner)
        html = self._share_html()
        self.assertIn('id="direct-link"', html)
        self.assertNotIn('still a Draft', html)

    def test_non_owner_editor_sees_no_publish(self):
        """
        GIVEN a draft survey and a non-owner editor collaborator
        WHEN the editor opens Share
        THEN no inline Publish control is shown, only a hint to ask the owner
        """
        editor = User.objects.create_user('gate_editor', password='pw')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        self._login(editor)
        html = self._share_html()
        self.assertNotIn('publishFromShare(this)', html)
        self.assertIn('Ask the survey owner to publish', html)

    def test_empty_draft_shows_blocked_reason(self):
        """
        GIVEN a draft survey with no questions
        WHEN its owner opens Share
        THEN the banner explains publishing is blocked, with no Publish button
        """
        empty = SurveyHeader.objects.create(
            name='emptydraft', organization=self.org, created_by=self.owner, status='draft',
        )
        self._login(self.owner)
        html = self._share_html(empty)
        self.assertIn('still a Draft', html)
        self.assertNotIn('publishFromShare(this)', html)
        self.assertIn('at least one section with questions', html)
