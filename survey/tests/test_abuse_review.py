"""Tests for the `abuse-review` capability (openspec/specs/abuse-review/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import Client
from django.contrib.auth.models import User
from unittest.mock import patch
from survey.models import SurveyHeader, SurveySession
from survey.content_screening import review_token as _cs_review_token
from survey.models import ContentReview, AbuseEvent, AuditLog
from survey.tests.helpers import _ContentScreeningBase


class ContentScreeningHoldGateTest(_ContentScreeningBase):
    """What respondents and the creator see while a survey is held."""

    def setUp(self):
        super().setUp()
        self._make_lure()
        self._publish()
        self.assertTrue(ContentReview.objects.filter(survey=self.survey, status='pending').exists())

    def test_anonymous_respondent_gets_the_unavailable_page_and_no_session(self):
        """
        GIVEN a held survey
        WHEN an anonymous visitor opens the entry URL and the section URL
        THEN both answer 404 with the unavailable page and no SurveySession is created
        """
        anon = self._anon()
        for url in (f'/surveys/{self.survey.uuid}/', f'/surveys/{self.survey.uuid}/s1/'):
            response = anon.get(url)
            self.assertEqual(response.status_code, 404, url)
            self.assertContains(response, 'available', status_code=404)
            self.assertNotContains(response, 'XFINITY', status_code=404)
        self.assertEqual(SurveySession.objects.filter(survey=self.survey).count(), 0)

    def test_owner_still_reaches_the_survey(self):
        """
        GIVEN a held survey
        WHEN its owner opens the respondent entry URL
        THEN the usual redirect to the first section is returned
        """
        self.assertEqual(self.client.get(f'/surveys/{self.survey.uuid}/').status_code, 302)

    def test_creator_banner_without_reasons(self):
        """
        GIVEN a held survey
        WHEN the owner opens the editor page
        THEN a review banner is shown and it lists none of the signals
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-testid="review-banner"')
        self.assertContains(response, 'being reviewed')
        body = response.content.decode()
        banner = body[body.index('review-banner'):body.index('review-banner') + 600]
        for word in ('shortener', 'brand', 'padding', 'score', 'xaply'):
            self.assertNotIn(word, banner.lower())

    def test_reported_only_survey_keeps_serving(self):
        """
        GIVEN a published survey with only a reported review
        WHEN an anonymous respondent opens it
        THEN the survey serves as usual
        """
        ContentReview.objects.filter(survey=self.survey).update(status='reported', source='report')
        self.assertEqual(self._anon().get(f'/surveys/{self.survey.uuid}/').status_code, 302)


class AbuseReviewPageTest(_ContentScreeningBase):
    """The staff review page and the two decisions."""

    def setUp(self):
        super().setUp()
        self._make_lure()
        self._publish()
        self.review = ContentReview.objects.get(survey=self.survey)
        self.url = f'/editor/abuse-review/{_cs_review_token(self.review)}/'
        self.staff = User.objects.create_user(username='screen_staff', password='pass', is_staff=True)
        self.staff_client = Client()
        self.staff_client.login(username='screen_staff', password='pass')
        AbuseEvent.objects.all().delete()

    def test_get_is_404_for_everyone_but_staff(self):
        """
        GIVEN the review link
        WHEN an anonymous client and the (non-staff) survey owner open it
        THEN both get 404 and the review is unchanged
        """
        self.assertEqual(self._anon().get(self.url).status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, 'pending')

    def test_bad_and_expired_tokens_are_404(self):
        """
        GIVEN a staff user
        WHEN a tampered token and an expired token are opened
        THEN both answer 404
        """
        self.assertEqual(self.staff_client.get('/editor/abuse-review/not-a-token/').status_code, 404)
        with patch('survey.content_screening.REVIEW_TOKEN_MAX_AGE', -1):
            self.assertEqual(self.staff_client.get(self.url).status_code, 404)

    def test_staff_sees_the_evidence(self):
        """
        GIVEN a staff user
        WHEN the review page is opened
        THEN it shows the signals, the account facts and both actions
        """
        response = self.staff_client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'shortener')
        self.assertContains(response, 'screen_owner')
        self.assertContains(response, 'value="release"')
        self.assertContains(response, 'value="confirm"')

    def test_release_restores_the_survey(self):
        """
        GIVEN a held survey
        WHEN staff posts release
        THEN the review is cleared with decided_by set, respondents reach the survey and a release AbuseEvent exists
        """
        response = self.staff_client.post(self.url, {'action': 'release'})
        self.assertEqual(response.status_code, 302)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, 'cleared')
        self.assertEqual(self.review.decided_by, self.staff)
        self.assertIsNotNone(self.review.decided_at)
        self.assertEqual(self._anon().get(f'/surveys/{self.survey.uuid}/').status_code, 302)
        self.assertTrue(AbuseEvent.objects.filter(defense='content_screen', detail__startswith=f'release survey={self.survey.id}').exists())

    def test_confirm_deactivates_the_account_and_closes_its_surveys(self):
        """
        GIVEN a held survey whose creator also has a draft and is logged in
        WHEN staff posts confirm
        THEN the creator is inactive, both surveys are closed with audit rows, the creator's session is gone, the review is confirmed and a confirm AbuseEvent exists
        """
        other = SurveyHeader.objects.create(name='screen_other', organization=self.org, created_by=self.owner)
        from django.contrib.sessions.models import Session
        self.assertEqual(sum(1 for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == str(self.owner.id)), 1)

        response = self.staff_client.post(self.url, {'action': 'confirm'})
        self.assertEqual(response.status_code, 302)

        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_active)
        self.survey.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((self.survey.status, other.status), ('closed', 'closed'))
        self.assertEqual(AuditLog.objects.filter(action='content_screen_close').count(), 2)
        self.assertEqual(sum(1 for s in Session.objects.all() if s.get_decoded().get('_auth_user_id') == str(self.owner.id)), 0)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, 'confirmed')
        self.assertTrue(AbuseEvent.objects.filter(
            defense='content_screen', detail__startswith=f'confirm survey={self.survey.id} user={self.owner.id}').exists())
        self.assertEqual(self.staff_client.get(self.url).status_code, 200)

    def test_decided_review_accepts_no_action(self):
        """
        GIVEN a released review
        WHEN staff posts confirm on it
        THEN nothing changes and the page shows the decision
        """
        self.staff_client.post(self.url, {'action': 'release'})
        self.staff_client.post(self.url, {'action': 'confirm'})
        self.review.refresh_from_db()
        self.owner.refresh_from_db()
        self.assertEqual(self.review.status, 'cleared')
        self.assertTrue(self.owner.is_active)
        self.assertContains(self.staff_client.get(self.url), 'Released')

    def test_admin_lists_the_pending_review_with_a_link(self):
        """
        GIVEN a superuser
        WHEN the ContentReview admin changelist is opened filtered by pending
        THEN the held survey appears with a link to the review page
        """
        admin_user = User.objects.create_superuser(username='screen_admin', password='pass', email='a@example.org')
        c = Client()
        c.login(username='screen_admin', password='pass')
        response = c.get('/admin/survey/contentreview/?status__exact=pending')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'screen_test')
        self.assertContains(response, '/editor/abuse-review/')
