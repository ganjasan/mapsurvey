"""Tests for the `survey-content-screening` capability (openspec/specs/survey-content-screening/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import SimpleTestCase, override_settings
from unittest.mock import patch
from survey.models import SurveyHeader, SurveySection
from django.conf import settings
from django.core import mail as _cs_mail
from survey.content_screening import score as _cs_score, fingerprint as _cs_fingerprint, hold_threshold as _cs_threshold
from survey.models import ContentReview, AbuseEvent
from survey.tests.helpers import _ContentScreeningBase, _TRACKER_URL, _XFINITY_SUBHEADING, _cs_input, _eager_notice


class ContentScoringTest(SimpleTestCase):
    """The scorer alone — no database, pinned to the 2026-10-02 scan."""

    def test_xfinity_lure_scores_above_threshold(self):
        """
        GIVEN the XFINITY lure: brand, "almost set", CLICK HERE link to a shortener, 74 empty paragraphs, one question, a two-minute-old account on a disposable domain
        WHEN it is scored
        THEN the score reaches the hold threshold and names shortener, brand, padding and external link
        """
        result = _cs_score(_cs_input(['Untitled survey', 'Section 1', _XFINITY_SUBHEADING, 'XFINITY'],
                                     questions=1, age_hours=0.03, domain='betterr.org'))
        self.assertGreaterEqual(result.score, _cs_threshold())
        keys = {s['key'] for s in result.signals}
        self.assertTrue({'shortener', 'brand', 'padding', 'external_link', 'disposable_domain'} <= keys, keys)

    def test_redirect_tracker_lure_scores_above_threshold(self):
        """
        GIVEN a survey whose only content is a question named "PDF Document" and a redirect_url on an email click tracker, published two minutes after registration
        WHEN it is scored
        THEN the score reaches the hold threshold and the tracker host from redirect_url is a signal
        """
        result = _cs_score(_cs_input(['PDF Document', 'PDF Document'], redirect=_TRACKER_URL, questions=1, age_hours=0.03))
        self.assertGreaterEqual(result.score, _cs_threshold())
        self.assertIn('tracker', {s['key'] for s in result.signals})

    def test_legitimate_surveys_from_the_scan_stay_below_threshold(self):
        """
        GIVEN the nine legitimate surveys the 2026-10-02 heuristic flagged (own S3 media, Facebook, a project site, a retailer image, "click here" in a real description)
        WHEN each is scored
        THEN none reaches the hold threshold
        """
        with override_settings(AWS_S3_CUSTOM_DOMAIN='mapsurvey-media-prod.s3.ap-southeast-2.amazonaws.com'):
            cases = [
                (['Stroud-Bristol coach', 'Click here to see the timetable <img src="https://mapsurvey-media-prod.s3.ap-southeast-2.amazonaws.com/x.png">'], '', 13, 0.01),
                (['Tahanan_Padayon', 'Follow us on <a href="https://www.facebook.com/tahanan">Facebook</a>'], '', 1, 0.1),
                (['Vrienden Weekend 2026', 'Zie <a href="https://ishet.al/weekend">de site</a>'], '', 1, 0.28),
                (['czy wiesz gdzie to jest', 'https://m.media-amazon.com/images/I/71dEnbFkofL.jpg'], '', 5, 0.04),
                (['The Bench Map', 'More at https://thebenchmap.ie'], '', 0, 0.2),
                (['Test Roy', 'varanger-ak.no'], '', 0, 0.27),
                (['Noise map', 'Where do you hear the most noise? Sign in to the council portal for details.'], '', 6, 300),
                (['Parking survey'], 'https://example-council.gov.uk/thanks', 4, 50),
                (['Heat survey', 'Mark where it feels hottest. Password for the gate is on the flyer.'], '', 3, 2),
            ]
            for texts, redirect, questions, age in cases:
                result = _cs_score(_cs_input(texts, redirect=redirect, questions=questions, age_hours=age))
                self.assertLess(result.score, _cs_threshold(), (texts[0], result.signals))

    def test_fresh_account_and_single_question_cannot_hold_alone(self):
        """
        GIVEN a one-question survey with no links or lure words from an account registered one minute ago
        WHEN it is scored
        THEN the score stays below the hold threshold
        """
        result = _cs_score(_cs_input(['My first survey', 'Where do you live?'], questions=1, age_hours=0.02))
        self.assertLess(result.score, _cs_threshold())

    def test_fingerprint_follows_the_text_not_the_account(self):
        """
        GIVEN two inputs with the same text and a different account age, and a third with a changed redirect_url
        WHEN fingerprinted
        THEN the first two match and the third differs
        """
        a = _cs_fingerprint(_cs_input(['A', 'B'], age_hours=0.1))
        b = _cs_fingerprint(_cs_input(['A', 'B'], age_hours=500))
        c = _cs_fingerprint(_cs_input(['A', 'B'], redirect='https://example.com/x'))
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class ContentScreeningFlowTest(_ContentScreeningBase):
    """Publish-time screening: hold, dedupe, fail-open, kill switch, live edits."""

    def test_publishing_a_lure_holds_it_and_mails_the_owner(self):
        """
        GIVEN a draft survey carrying the XFINITY lure
        WHEN the owner publishes it
        THEN the publish succeeds, one pending review exists, one hold AbuseEvent is written and one mail reaches ABUSE_REVIEW_EMAIL with the review link and signals
        """
        self._make_lure()
        response = self._publish()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.survey.status, 'published')
        review = ContentReview.objects.get(survey=self.survey)
        self.assertEqual((review.status, review.source, review.trigger), ('pending', 'screen', 'publish'))
        self.assertGreaterEqual(review.score, _cs_threshold())
        events = AbuseEvent.objects.filter(defense='content_screen')
        self.assertEqual(events.count(), 1)
        self.assertTrue(events[0].detail.startswith(f'hold survey={self.survey.id} score='))
        self.assertEqual(len(_cs_mail.outbox), 1)
        msg = _cs_mail.outbox[0]
        self.assertEqual(msg.to, [settings.ABUSE_REVIEW_EMAIL])
        self.assertIn('screen_test', msg.subject)
        self.assertIn(str(review.score), msg.subject)
        self.assertIn('/editor/abuse-review/', msg.body)
        self.assertIn('shortener', msg.body)

    def test_second_publish_while_pending_creates_nothing_new(self):
        """
        GIVEN a held survey
        WHEN it goes back to draft and is published again
        THEN the same review row is updated and no second mail is sent
        """
        self._make_lure()
        self._publish()
        self._transition('draft')
        self._publish()
        self.assertEqual(ContentReview.objects.filter(survey=self.survey).count(), 1)
        self.assertEqual(len(_cs_mail.outbox), 1)

    def test_clean_survey_leaves_no_trace(self):
        """
        GIVEN an ordinary survey
        WHEN it is published
        THEN no review row, no AbuseEvent and no mail exist
        """
        self._publish()
        self.assertFalse(ContentReview.objects.exists())
        self.assertFalse(AbuseEvent.objects.filter(defense='content_screen').exists())
        self.assertEqual(len(_cs_mail.outbox), 0)

    def test_scorer_exception_does_not_block_publishing(self):
        """
        GIVEN a scorer that raises
        WHEN the owner publishes a lure
        THEN the publish completes as usual and no review exists
        """
        self._make_lure()
        with patch('survey.content_screening.collect_text', side_effect=RuntimeError('boom')):
            response = self._publish()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.survey.status, 'published')
        self.assertFalse(ContentReview.objects.exists())

    @override_settings(CONTENT_SCREENING=False)
    def test_kill_switch_off_skips_screening(self):
        """
        GIVEN CONTENT_SCREENING off
        WHEN a lure is published
        THEN no review is created and anonymous respondents reach the survey
        """
        self._make_lure()
        self._publish()
        self.assertFalse(ContentReview.objects.exists())
        self.assertEqual(self._anon().get(f'/surveys/{self.survey.uuid}/').status_code, 302)

    @override_settings(CONTENT_SCREENING=False)
    def test_kill_switch_off_keeps_an_existing_hold(self):
        """
        GIVEN a survey with a pending review and CONTENT_SCREENING off
        WHEN an anonymous respondent opens it
        THEN the unavailable page is still served
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        ContentReview.objects.create(survey=self.survey, status='pending', score=9)
        self.assertEqual(self._anon().get(f'/surveys/{self.survey.uuid}/').status_code, 404)

    def test_testing_transition_is_not_screened(self):
        """
        GIVEN a lure survey
        WHEN the owner moves it to testing
        THEN no review is created
        """
        self._make_lure()
        with _eager_notice():
            self._transition('testing')
        self.assertFalse(ContentReview.objects.exists())

    def test_live_redirect_edit_rescreens_a_published_survey(self):
        """
        GIVEN a published survey that passed screening with a "PDF Document" question
        WHEN the owner sets redirect_url to an email click tracker through the settings panel
        THEN a pending review with trigger live_edit is created
        """
        self.question.name = 'PDF Document'
        self.question.save(update_fields=['name'])
        self._publish()
        self.assertFalse(ContentReview.objects.exists())
        with _eager_notice():
            response = self.client.post(
                f'/editor/surveys/{self.survey.uuid}/settings-panel/',
                {'name': 'screen_test', 'visibility': 'private', 'redirect_url': _TRACKER_URL},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
        self.assertEqual(response.status_code, 200, response.content[:300])
        review = ContentReview.objects.get(survey=self.survey)
        self.assertEqual((review.status, review.trigger), ('pending', 'live_edit'))

    def test_released_content_is_not_held_again_until_it_changes(self):
        """
        GIVEN a held survey the owner released
        WHEN it is republished unchanged, and then republished with a changed thanks page
        THEN the unchanged publish creates no review and the changed one creates a new pending review
        """
        self._make_lure()
        self._publish()
        review = ContentReview.objects.get(survey=self.survey)
        review.status = 'cleared'
        review.save(update_fields=['status'])
        self._transition('draft')
        self._publish()
        self.assertEqual(ContentReview.objects.filter(survey=self.survey).count(), 1)
        self.survey.thanks_html = {'en': '<p>Verify your password at <a href="https://bit.ly/zz">bit.ly</a></p>'}
        self.survey.save(update_fields=['thanks_html'])
        self._transition('draft')
        self._publish()
        self.assertEqual(ContentReview.objects.filter(survey=self.survey, status='pending').count(), 1)

    def test_draft_publish_anchors_the_review_to_the_canonical_survey(self):
        """
        GIVEN a published survey with a draft copy that received the lure
        WHEN the draft is published
        THEN the pending review points at the canonical survey with trigger draft_publish
        """
        self._publish()
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/create-draft/')
        draft = SurveyHeader.objects.get(published_version=self.survey)
        section = SurveySection.objects.get(survey_header=draft, is_head=True)
        section.subheading = _XFINITY_SUBHEADING
        section.save(update_fields=['subheading'])
        with _eager_notice():
            response = self.client.post(f'/editor/surveys/{draft.uuid}/publish-draft/', {'ack_translation_gaps': 'true'})
        self.assertEqual(response.status_code, 302, response.content[:300])
        review = ContentReview.objects.get()
        self.assertEqual(review.survey_id, self.survey.id)
        self.assertEqual(review.trigger, 'draft_publish')

    def test_broker_failure_sends_the_notice_inline(self):
        """
        GIVEN a Celery broker that refuses the task
        WHEN a lure is published
        THEN the mail is still sent and the review stays pending
        """
        self._make_lure()
        with patch('survey.tasks.send_abuse_review_notice.delay', side_effect=OSError('broker down')):
            self._transition('published')
        self.assertEqual(ContentReview.objects.get().status, 'pending')
        self.assertEqual(len(_cs_mail.outbox), 1)

    def test_notice_never_goes_to_the_creator_and_names_no_email(self):
        """
        GIVEN a lure published by a creator with an email address
        WHEN the notice is sent
        THEN only the review address receives it and the AbuseEvent detail carries no email or username
        """
        self._make_lure()
        self._publish()
        for msg in _cs_mail.outbox:
            self.assertNotIn(self.owner.email, msg.to)
        for ev in AbuseEvent.objects.filter(defense='content_screen'):
            self.assertNotIn('@', ev.detail)
            self.assertNotIn(self.owner.username, ev.detail)
