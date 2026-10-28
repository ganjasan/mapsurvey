"""Tests for the `pro-interest-capture` capability (openspec/specs/pro-interest-capture/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from unittest import mock
from survey.models import SurveyEvent


class ProEarlyAccessPageTest(TestCase):
    """`/pro/` — the questionnaire that decides what a paid tier should be.

    The page is a research instrument, so the tests guard the dataset as much as
    the rendering: an unknown capability key must fail loudly rather than vanish,
    an empty selection must survive as a real answer, and an analytics outage
    must never cost us a submission.
    """

    def setUp(self):
        from survey.pro_interest import CAPABILITY_KEYS

        self.capability_keys = CAPABILITY_KEYS

    def _payload(self, **overrides):
        data = {
            'email': 'planner@example.org',
            'organisation': 'City of Example',
            'segment': 'public_body',
            'capabilities': ['own_domain', 'eu_hosting'],
            'missing_text': 'We had to copy every block by hand.',
            'budget_shape': 'project_grant',
            'consent': '1',
        }
        data.update(overrides)
        return data

    def test_anonymous_visitor_sees_every_capability_group(self):
        """
        GIVEN the Pro early-access page
        WHEN an unauthenticated visitor requests it
        THEN it renders with every capability group and every option key
        """
        from survey.pro_interest import CAPABILITY_GROUPS

        resp = Client().get("/pro/")
        self.assertEqual(resp.status_code, 200)
        for group in CAPABILITY_GROUPS:
            self.assertContains(resp, str(group['label']))
            for key, _label, _hint in group['options']:
                self.assertContains(resp, f'value="{key}"')

    def test_page_quotes_no_price(self):
        """
        GIVEN the Pro page exists to open a conversation, not to sell
        WHEN it is rendered
        THEN no currency amount and no billing period appear in the copy

        "per project" is deliberately NOT forbidden: the page uses it to say the
        project service already does some of this by hand, which is a delivery
        model, not a price.
        """
        import re as _re

        body = Client().get("/pro/").content.decode()
        for token in ('€', '£', 'per month', 'per year', '/month', '/mo'):
            self.assertNotIn(token, body)
        self.assertIsNone(_re.search(r'[€$£]\s?\d', body))

    def test_page_promises_free_stays_free(self):
        """
        GIVEN the landing and /services/ both say the platform is not a paywall
        WHEN the Pro page is rendered
        THEN it repeats that free capabilities stay free
        """
        self.assertContains(Client().get("/pro/"), "stays free")

    def test_consent_box_is_present_and_unticked(self):
        """
        GIVEN the page collects an email while arguing we can sign a DPA
        WHEN it is rendered
        THEN a consent checkbox is present, unchecked, and a privacy link is shown
        """
        resp = Client().get("/pro/")
        self.assertContains(resp, 'name="consent"')
        self.assertNotContains(resp, 'name="consent" value="1" checked')
        self.assertContains(resp, '/trust/#data-privacy')

    def test_valid_submission_is_stored(self):
        """
        GIVEN a visitor filling the questionnaire
        WHEN they submit with consent and two capabilities
        THEN a ProInterest row holds both keys and the confirmation is shown
        """
        from survey.models import ProInterest

        resp = Client().post("/pro/", self._payload())
        self.assertEqual(resp.status_code, 200)
        interest = ProInterest.objects.get()
        self.assertEqual(sorted(interest.capabilities), ['eu_hosting', 'own_domain'])
        self.assertEqual(interest.segment, 'public_body')
        self.assertEqual(interest.budget_shape, 'project_grant')
        self.assertIsNotNone(interest.consent_at)
        self.assertContains(resp, "Thank you")

    def test_empty_capability_selection_is_a_real_answer(self):
        """
        GIVEN "none of this matters to me" is as useful as a full sheet
        WHEN a visitor submits with no capability ticked
        THEN the row is created with an empty list rather than rejected
        """
        from survey.models import ProInterest

        Client().post("/pro/", self._payload(capabilities=[]))
        self.assertEqual(ProInterest.objects.get().capabilities, [])

    def test_unknown_capability_key_is_rejected(self):
        """
        GIVEN a key the template and the constant disagree about
        WHEN it is submitted
        THEN nothing is stored, so the dataset cannot rot silently
        """
        from survey.models import ProInterest

        resp = Client().post("/pro/", self._payload(
            capabilities=['own_domain', 'free_ponies'],
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProInterest.objects.count(), 0)

    def test_submission_without_consent_is_rejected(self):
        """
        GIVEN consent is what makes storing the email lawful
        WHEN a visitor submits without ticking it
        THEN the form is redisplayed with an error and nothing is stored
        """
        from survey.models import ProInterest

        payload = self._payload()
        del payload['consent']
        resp = Client().post("/pro/", payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProInterest.objects.count(), 0)
        self.assertContains(resp, "could not save")

    def test_authenticated_visitor_is_prefilled_and_attributed(self):
        """
        GIVEN a signed-in creator
        WHEN they load and then submit the page
        THEN their email is pre-filled and the stored row references them
        """
        from survey.models import ProInterest

        user = User.objects.create_user(
            username='creator', email='creator@example.org', password='pw',
        )
        c = Client()
        c.force_login(user)
        self.assertContains(c.get("/pro/"), 'creator@example.org')
        c.post("/pro/", self._payload())
        self.assertEqual(ProInterest.objects.get().user, user)

    def test_submission_writes_no_respondent_analytics(self):
        """
        GIVEN SurveyEvent measures our customers' respondents, not us
        WHEN a Pro interest is stored
        THEN no SurveyEvent row is created
        """
        from survey.models import SurveyEvent

        before = SurveyEvent.objects.count()
        Client().post("/pro/", self._payload())
        self.assertEqual(SurveyEvent.objects.count(), before)

    def test_analytics_failure_does_not_lose_the_answer(self):
        """
        GIVEN analytics that can break a request is worse than no analytics
        WHEN emitting the PostHog event raises
        THEN the submission is still stored and the visitor still sees thanks
        """
        from survey.models import ProInterest

        with mock.patch('posthog.disabled', False), \
                mock.patch('posthog.capture', side_effect=RuntimeError('down')):
            resp = Client().post("/pro/", self._payload())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProInterest.objects.count(), 1)
        self.assertContains(resp, "Thank you")

    def test_submission_emits_one_product_event(self):
        """
        GIVEN the answers must be countable, not only readable one by one
        WHEN a submission is stored
        THEN one pro_interest_submitted event carries segment, keys and budget
        """
        with mock.patch('posthog.disabled', False), \
                mock.patch('posthog.capture') as capture:
            Client().post("/pro/", self._payload())
        self.assertEqual(capture.call_count, 1)
        args, kwargs = capture.call_args
        self.assertEqual(args[0], 'pro_interest_submitted')
        self.assertEqual(kwargs['properties']['segment'], 'public_body')
        self.assertEqual(kwargs['properties']['budget_shape'], 'project_grant')
        self.assertEqual(
            sorted(kwargs['properties']['capabilities']),
            ['eu_hosting', 'own_domain'],
        )

    def test_pro_and_services_are_reachable_and_crawlable(self):
        """
        GIVEN /services/ was live for weeks with no internal link to it
        WHEN a landing page, robots.txt and sitemap.xml are fetched
        THEN nav and footer link pricing and services, and /pricing/, /pro/ and /services/
             are crawlable (change pricing-page: /pro/ is linked from /pricing/)
        """
        c = Client()
        landing = c.get("/")
        self.assertContains(landing, 'href="/pricing/"')
        self.assertContains(landing, 'href="/services/"')
        self.assertContains(c.get("/pricing/"), 'href="/pro/"')
        robots = c.get("/robots.txt")
        self.assertContains(robots, "Allow: /pro/")
        self.assertContains(robots, "Allow: /pricing/")
        sitemap = c.get("/sitemap.xml")
        self.assertContains(sitemap, "/pro/")
        self.assertContains(sitemap, "/pricing/")
        self.assertContains(sitemap, "/services/")
