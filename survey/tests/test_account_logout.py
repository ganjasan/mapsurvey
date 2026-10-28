"""Tests for the `account-logout` capability (openspec/specs/account-logout/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
import re
from survey.models import SurveyHeader, Membership
from survey.tests.helpers import _make_org


class LogoutTest(TestCase):
    """Logout is a POST (change fix-logout-post, #432): Django 5 answers GET with 405."""

    def setUp(self):
        self.org = _make_org('Logout Org')
        self.user = User.objects.create_user(username='logout_user', password='testpass123')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='logout_survey', organization=self.org)
        self.client.login(username='logout_user', password='testpass123')

    def test_post_signs_out_and_redirects_home(self):
        """
        GIVEN a signed-in creator
        WHEN they POST to the logout URL
        THEN they are redirected to / and the session is anonymous
        """
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_does_not_sign_out(self):
        """
        GIVEN a signed-in creator
        WHEN they request the logout URL with GET
        THEN the session stays signed in
        """
        self.client.get(reverse('logout'))
        self.assertEqual(self.client.session.get('_auth_user_id'), str(self.user.pk))

    def test_pages_render_post_form_and_no_get_link(self):
        """
        GIVEN a signed-in creator
        WHEN they open the dashboard, a survey editor page and a landing page
        THEN each page has a POST logout form with a CSRF token and no link to the logout URL
        """
        logout_url = reverse('logout')
        form = re.compile(
            r'<form method="post" action="%s"[^>]*>\s*<input type="hidden" name="csrfmiddlewaretoken"'
            % re.escape(logout_url))
        link = re.compile(r'<a\b[^>]*href="%s"' % re.escape(logout_url))
        for url in (reverse('editor'),
                    reverse('editor_survey_detail', args=[self.survey.uuid]),
                    reverse('community_engagement_platform')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertRegex(html, form)
                self.assertNotRegex(html, link)
