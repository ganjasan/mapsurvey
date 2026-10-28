"""Tests for the `respondent-abuse-report` capability (openspec/specs/respondent-abuse-report/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
import uuid
from survey.models import SurveyHeader
from django.core import mail as _cs_mail
from survey.models import ContentReview, AbuseEvent
from survey.tests.helpers import _ContentScreeningBase, _eager_notice


class RespondentReportTest(_ContentScreeningBase):
    """The safety footer and the report form."""

    def setUp(self):
        super().setUp()
        self._publish()
        self.report_url = f'/surveys/{self.survey.uuid}/report/'

    def test_footer_on_section_and_thanks_pages(self):
        """
        GIVEN a published survey
        WHEN a respondent opens a section page and the thanks page
        THEN both carry the safety notice and the report link
        """
        anon = self._anon()
        for url in (f'/surveys/{self.survey.uuid}/s1/', f'/surveys/{self.survey.uuid}/thanks/'):
            response = anon.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, 'Never enter passwords')
            self.assertContains(response, self.report_url)

    def test_first_report_opens_a_review_and_mails_once(self):
        """
        GIVEN a published survey with no open review
        WHEN a respondent reports it as phishing
        THEN a reported review with report_count 1 exists, one mail is sent, a report AbuseEvent is written and the survey still serves
        """
        with _eager_notice():
            response = self._anon().post(self.report_url, {'reason': 'phishing', 'message': 'asks for my password'},
                                         REMOTE_ADDR='10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thank you')
        review = ContentReview.objects.get(survey=self.survey)
        self.assertEqual((review.status, review.source, review.report_count), ('reported', 'report', 1))
        self.assertEqual(len(_cs_mail.outbox), 1)
        self.assertIn('reported', _cs_mail.outbox[0].subject)
        self.assertTrue(AbuseEvent.objects.filter(detail__startswith=f'report survey={self.survey.id}').exists())
        self.assertEqual(self._anon().get(f'/surveys/{self.survey.uuid}/').status_code, 302)

    def test_repeated_reports_count_but_do_not_mail(self):
        """
        GIVEN a survey already reported
        WHEN a second report arrives from another address
        THEN report_count becomes 2 and no second mail is sent
        """
        with _eager_notice():
            self._anon().post(self.report_url, {'reason': 'scam'}, REMOTE_ADDR='10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3]))
            self._anon().post(self.report_url, {'reason': 'other', 'message': 'odd'}, REMOTE_ADDR='10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3]))
        self.assertEqual(ContentReview.objects.get(survey=self.survey).report_count, 2)
        self.assertEqual(len(_cs_mail.outbox), 1)

    def test_fourth_report_from_one_address_is_rate_limited(self):
        """
        GIVEN three reports from one IP within an hour
        WHEN a fourth arrives
        THEN it answers 429 and the review is not touched
        """
        # The counter lives in Redis and outlives the test database, so a fixed
        # IP would carry the previous run's budget into this one.
        ip = '10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3])
        with _eager_notice():
            for _ in range(3):
                self.assertEqual(self._anon().post(self.report_url, {'reason': 'scam'}, REMOTE_ADDR=ip).status_code, 200)
            response = self._anon().post(self.report_url, {'reason': 'scam'}, REMOTE_ADDR=ip)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(ContentReview.objects.get(survey=self.survey).report_count, 3)

    def test_unknown_and_draft_surveys_are_404(self):
        """
        GIVEN a UUID that names nothing and a draft survey
        WHEN their report pages are requested
        THEN both answer 404
        """
        self.assertEqual(self._anon().get(f'/surveys/{uuid.uuid4()}/report/').status_code, 404)
        draft = SurveyHeader.objects.create(name='screen_draft', organization=self.org, created_by=self.owner)
        self.assertEqual(self._anon().get(f'/surveys/{draft.uuid}/report/').status_code, 404)


class ReportReasonsAndEscalationTest(_ContentScreeningBase):
    """Seven report reasons; child-abuse reports always reach the moderator, urgently."""

    def setUp(self):
        super().setUp()
        self._publish()
        self.report_url = f'/surveys/{self.survey.uuid}/report/'

    def _ip(self):
        return '10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3])

    def test_form_offers_seven_reasons_in_order(self):
        """
        GIVEN a published survey
        WHEN the report page is opened
        THEN it offers phishing, scam, illegal, child_abuse, harassment, personal_data, other in that order
        """
        html = self._anon().get(self.report_url).content.decode()
        positions = [html.index(f'value="{code}"') for code in
                     ('phishing', 'scam', 'illegal', 'child_abuse', 'harassment', 'personal_data', 'other')]
        self.assertEqual(positions, sorted(positions))

    def test_first_child_abuse_report_mails_urgently(self):
        """
        GIVEN a survey with no open review
        WHEN a respondent reports child abuse
        THEN exactly one notice is sent and its subject starts with [URGENT]
        """
        with _eager_notice():
            self._anon().post(self.report_url, {'reason': 'child_abuse'}, REMOTE_ADDR=self._ip())
        self.assertEqual(len(_cs_mail.outbox), 1)
        self.assertTrue(_cs_mail.outbox[0].subject.startswith('[URGENT]'))

    def test_child_abuse_after_scam_escalates_once(self):
        """
        GIVEN a survey already reported as a scam (one notice sent)
        WHEN a child-abuse report arrives, then another one
        THEN the review note now starts with child_abuse:, report_count is 3, and exactly one more notice is sent, marked [URGENT]
        """
        with _eager_notice():
            self._anon().post(self.report_url, {'reason': 'scam'}, REMOTE_ADDR=self._ip())
            self._anon().post(self.report_url, {'reason': 'child_abuse', 'message': 'photos'}, REMOTE_ADDR=self._ip())
            self._anon().post(self.report_url, {'reason': 'child_abuse'}, REMOTE_ADDR=self._ip())
        review = ContentReview.objects.get(survey=self.survey)
        self.assertTrue(review.note.startswith('child_abuse:'))
        self.assertIn('scam', review.note)
        self.assertEqual(review.report_count, 3)
        self.assertEqual(len(_cs_mail.outbox), 2)
        self.assertTrue(_cs_mail.outbox[1].subject.startswith('[URGENT]'))
