"""Tests that no capability owns yet: htmx-section-navigation.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.tests.helpers import _make_org


class HTMXNavigationTest(TestCase):
    """Tests for HTMX-based section navigation with persistent map."""

    def setUp(self):
        self.org = _make_org('HTMXOrg')
        self.user = User.objects.create_user(username='htmxuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='htmx_test', organization=self.org, created_by=self.user,
            status='published',
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey, name='sec2', title='Section 2',
            code='S2',
        )
        self.section1.next_section = self.section2
        self.section1.save()
        self.section2.prev_section = self.section1
        self.section2.save()
        Question.objects.create(
            survey_section=self.section1, code='Q1', order_number=1,
            name='Fav color', input_type='text',
        )
        Question.objects.create(
            survey_section=self.section2, code='Q2', order_number=1,
            name='Fav city', input_type='text',
        )

    def test_htmx_get_returns_partial(self):
        """
        GIVEN a published survey with sections
        WHEN a section is loaded with HX-Request header
        THEN the response contains section-data div but NOT <head> tag
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        resp = self.client.get(
            f'/surveys/{self.survey.uuid}/sec1/',
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="section-data"')
        self.assertNotContains(resp, '<head>')

    def test_regular_get_returns_full_page(self):
        """
        GIVEN a published survey
        WHEN a section is loaded without HX-Request header
        THEN the response contains the full page with <head> and map init
        """
        resp = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<head>')
        self.assertContains(resp, '_initialMapState')
        self.assertContains(resp, 'id="section-data"')

    def test_htmx_post_returns_next_section_partial(self):
        """
        GIVEN a respondent on section 1
        WHEN the form is submitted via HTMX POST
        THEN the response contains section 2's partial (not a redirect)
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        resp = self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {'Q1': 'Blue'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Section 2')
        self.assertContains(resp, 'data-section-current="2"')

    def test_htmx_post_last_section_returns_hx_redirect(self):
        """
        GIVEN a respondent on the last section
        WHEN the form is submitted via HTMX POST
        THEN the response has HX-Redirect header to thanks page
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {'Q1': 'Blue'},
            HTTP_HX_REQUEST='true',
        )
        resp = self.client.post(
            f'/surveys/{self.survey.uuid}/sec2/',
            {'Q2': 'Berlin'},
            HTTP_HX_REQUEST='true',
        )
        self.assertIn('HX-Redirect', resp)
        self.assertIn('thanks', resp['HX-Redirect'])

    def test_non_htmx_post_returns_redirect(self):
        """
        GIVEN a respondent on section 1
        WHEN the form is submitted without HTMX
        THEN the response is a regular redirect to section 2
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        resp = self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {'Q1': 'Blue'},
        )
        self.assertEqual(resp.status_code, 302)

    def test_htmx_back_navigation_returns_partial(self):
        """
        GIVEN a respondent who navigated to section 2
        WHEN section 1 is loaded via HTMX GET (back button)
        THEN the response contains section 1's partial with existing answers
        """
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.client.post(
            f'/surveys/{self.survey.uuid}/sec1/',
            {'Q1': 'Blue'},
        )
        resp = self.client.get(
            f'/surveys/{self.survey.uuid}/sec1/',
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="section-data"')
        self.assertContains(resp, 'data-section-current="1"')
