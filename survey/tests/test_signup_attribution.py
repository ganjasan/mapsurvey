"""Tests for the `signup-attribution` capability (openspec/specs/signup-attribution/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from survey.models import SurveyHeader, SurveySection
from survey.funnel import CreatorFunnelService
from django.test import RequestFactory
from survey.models import SignupAttribution
from survey.events import capture_signup_source, persist_signup_attribution
from io import StringIO
from django.core.management import call_command
from unittest.mock import patch as _ai_patch
from django.core import signing as _signing
from django.test import RequestFactory as _AIRequestFactory
from django_registration.signals import user_registered as _user_registered
from survey import product_events as _pe
from survey.events import FIRST_TOUCH_COOKIE, classify_source, encode_first_touch, first_touch_for_signup
from survey.models import SignupAttribution as _SA
from survey.tests.helpers import _make_org


class SignupAttributionCaptureTest(TestCase):
    """Phase 1: capture + persist a creator's acquisition source at registration."""

    def setUp(self):
        self.rf = RequestFactory()

    def test_capture_then_persist_records_referrer_and_utm(self):
        """
        GIVEN a visitor arriving from reddit with UTM params
        WHEN capture runs on the page load and persist runs at registration
        THEN a SignupAttribution stores the classified bucket and the UTM triple
        """
        req = self.rf.get("/register/?utm_source=edu&utm_medium=email&utm_campaign=fall",
                          HTTP_REFERER="https://www.reddit.com/r/urbanplanning")
        req.session = {}
        capture_signup_source(req)
        user = User.objects.create_user("cap_u", password="x")
        persist_signup_attribution(user, req)

        a = SignupAttribution.objects.get(user=user)
        self.assertEqual(a.source_bucket, "social")       # reddit -> social bucket
        self.assertEqual(a.utm_source, "edu")
        self.assertEqual(a.utm_medium, "email")
        self.assertEqual(a.utm_campaign, "fall")
        self.assertIn("reddit", a.raw_referrer)

    def test_direct_visit_records_direct(self):
        """
        GIVEN a visitor with no referrer and no UTM
        WHEN capture + persist run
        THEN attribution is recorded as direct with empty UTM (absence, not error)
        """
        req = self.rf.get("/register/")
        req.session = {}
        capture_signup_source(req)
        user = User.objects.create_user("direct_u", password="x")
        persist_signup_attribution(user, req)

        a = SignupAttribution.objects.get(user=user)
        self.assertEqual(a.source_bucket, "direct")
        self.assertEqual(a.utm_source, "")

    def test_persist_is_idempotent(self):
        """
        GIVEN a user who already has an attribution row
        WHEN persist runs again
        THEN it neither duplicates nor raises (fail-open)
        """
        req = self.rf.get("/register/")
        req.session = {}
        user = User.objects.create_user("idem_u", password="x")
        persist_signup_attribution(user, req)
        persist_signup_attribution(user, req)
        self.assertEqual(SignupAttribution.objects.filter(user=user).count(), 1)


class SignupsBySourceTest(TestCase):
    """Dashboard source breakdown from SignupAttribution."""

    def test_available_false_before_any_attribution(self):
        """
        GIVEN no attribution rows
        WHEN signups_by_source runs
        THEN available is False (panel shows the pre-Phase-1 placeholder)
        """
        self.assertFalse(CreatorFunnelService().signups_by_source()["available"])

    def test_groups_recent_signups_and_unknown_bucket(self):
        """
        GIVEN recent users: two attributed to 'edu', one with no attribution
        WHEN signups_by_source runs
        THEN it groups by source and puts the unattributed user under 'unknown'
        """
        for i in range(2):
            u = User.objects.create_user(f"edu_{i}", password="x")
            SignupAttribution.objects.create(user=u, utm_source="edu", source_bucket="other")
        User.objects.create_user("noattr", password="x")   # recent, no attribution

        res = CreatorFunnelService().signups_by_source()
        self.assertTrue(res["available"])
        by = {r["source"]: r["regs"] for r in res["rows"]}
        self.assertEqual(by.get("edu"), 2)
        self.assertEqual(by.get("unknown"), 1)


class SourceClassificationTest(TestCase):
    """classify_source: referrer buckets plus the UTM promotion to `ai`."""

    def test_ai_assistant_referrers(self):
        """
        GIVEN referrers from ChatGPT, Perplexity and Gemini
        WHEN classify_source runs
        THEN every one lands in the `ai` bucket
        """
        for url in ('https://chatgpt.com/', 'https://www.perplexity.ai/search?q=x',
                    'https://gemini.google.com/app'):
            self.assertEqual(classify_source(url)[1], 'ai', url)

    def test_chatgpt_utm_without_referrer(self):
        """
        GIVEN no referrer and utm_source=chatgpt.com (how ChatGPT tags its links)
        WHEN classify_source runs
        THEN the bucket is `ai`, not `direct`
        """
        self.assertEqual(classify_source('', 'chatgpt.com'), ('', 'ai'))

    def test_secondary_search_engines(self):
        """
        GIVEN DuckDuckGo, Brave and Ecosia referrers
        WHEN classify_source runs
        THEN the bucket is `search_other`
        """
        for url in ('https://duckduckgo.com/', 'https://search.brave.com/search?q=x',
                    'https://www.ecosia.org/search?q=x'):
            self.assertEqual(classify_source(url)[1], 'search_other', url)

    def test_google_bing_and_email_unchanged(self):
        """
        GIVEN Google, Bing and Gmail referrers
        WHEN classify_source runs
        THEN the historical buckets are kept, and Gmail is email rather than google
        """
        self.assertEqual(classify_source('https://www.google.com/search?q=x')[1], 'google')
        self.assertEqual(classify_source('https://www.bing.com/search')[1], 'bing')
        self.assertEqual(classify_source('https://mail.google.com/mail/u/0/')[1], 'email')

    def test_own_host_is_direct(self):
        """
        GIVEN the site's own host as the referrer (an internal hop)
        WHEN classify_source runs with the own host
        THEN the result is direct with no host recorded
        """
        self.assertEqual(
            classify_source('https://mapsurvey.org/for-planners/', own_host='mapsurvey.org'),
            ('', 'direct'),
        )


class FirstTouchCookieTest(TestCase):
    """FirstTouchMiddleware writes the cookie on marketing pages only."""

    def setUp(self):
        self.org = _make_org('FirstTouchOrg')
        self.survey = SurveyHeader.objects.create(
            name='ft_survey', organization=self.org, redirect_url='#', status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='section1',
            start_map_postion=Point(0, 0), start_map_zoom=10,
        )

    def test_landing_sets_signed_cookie_with_source(self):
        """
        GIVEN a first visit to the landing page from ChatGPT
        WHEN the response is served
        THEN a signed ms_ft cookie holds the ai bucket, the host and the landing path
        """
        response = self.client.get('/', HTTP_REFERER='https://chatgpt.com/c/abc')
        self.assertEqual(response.status_code, 200)
        cookie = response.cookies.get(FIRST_TOUCH_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie['httponly'])
        data = _signing.loads(cookie.value, salt='survey.first_touch')
        self.assertEqual(data['b'], 'ai')
        self.assertEqual(data['h'], 'chatgpt.com')
        self.assertEqual(data['p'], '/')

    def test_existing_cookie_is_not_overwritten(self):
        """
        GIVEN a visitor who already carries a first-touch cookie
        WHEN they load another marketing page from Google
        THEN the cookie is left alone (first touch wins)
        """
        self.client.cookies[FIRST_TOUCH_COOKIE] = encode_first_touch({'b': 'ai', 'h': 'chatgpt.com'})
        response = self.client.get('/', HTTP_REFERER='https://www.google.com/')
        self.assertNotIn(FIRST_TOUCH_COOKIE, response.cookies)

    def test_respondent_pages_never_set_it(self):
        """
        GIVEN a respondent opening a survey page
        WHEN the response is served
        THEN no first-touch cookie is written
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/section1/', HTTP_REFERER='https://www.google.com/')
        self.assertNotIn(FIRST_TOUCH_COOKIE, response.cookies)

    def test_register_form_page_sets_it(self):
        """
        GIVEN a visitor landing straight on the registration form from an outreach link
        WHEN the page is served
        THEN the cookie records the UTM source
        """
        response = self.client.get('/accounts/register/?utm_source=edu&utm_medium=email')
        cookie = response.cookies.get(FIRST_TOUCH_COOKIE)
        self.assertIsNotNone(cookie)
        data = _signing.loads(cookie.value, salt='survey.first_touch')
        self.assertEqual(data['s'], 'edu')
        self.assertEqual(data['m'], 'email')


class FirstTouchPersistenceTest(TestCase):
    """persist_signup_attribution reads the cookie and never the request's own referrer."""

    def setUp(self):
        self.rf = _AIRequestFactory()

    def _req(self, cookie=None, referer=''):
        req = self.rf.get('/accounts/register/', HTTP_REFERER=referer)
        req.session = {}
        if cookie is not None:
            req.COOKIES[FIRST_TOUCH_COOKIE] = encode_first_touch(cookie)
        return req

    def test_cookie_wins_over_internal_referrer(self):
        """
        GIVEN a cookie captured from ChatGPT twelve days ago and a registration request
              whose only referrer is the site itself
        WHEN attribution is persisted
        THEN the row carries the ai bucket, the UTM and the landing path from the cookie
        """
        req = self._req(
            cookie={'r': 'https://chatgpt.com/', 'h': 'chatgpt.com', 'b': 'ai',
                    's': 'chatgpt.com', 'm': '', 'c': '', 'p': '/for-planners/', 't': 1},
            referer='http://testserver/accounts/register/',
        )
        user = User.objects.create_user('ft_cookie', password='x')
        persist_signup_attribution(user, req)
        a = _SA.objects.get(user=user)
        self.assertEqual(a.source_bucket, 'ai')
        self.assertEqual(a.utm_source, 'chatgpt.com')
        self.assertEqual(a.landing_path, '/for-planners/')
        self.assertIn('chatgpt', a.raw_referrer)

    def test_internal_referrer_alone_is_direct(self):
        """
        GIVEN no cookie, no session value and the site itself as referrer
        WHEN attribution is persisted
        THEN the source is direct and the site's host is not stored
        """
        req = self._req(referer='http://testserver/')
        user = User.objects.create_user('ft_internal', password='x')
        persist_signup_attribution(user, req)
        a = _SA.objects.get(user=user)
        self.assertEqual(a.source_bucket, 'direct')
        self.assertEqual(a.raw_referrer, '')

    def test_tampered_cookie_is_ignored(self):
        """
        GIVEN a cookie whose signature does not verify
        WHEN first_touch_for_signup resolves the source
        THEN it falls through to direct instead of trusting the payload
        """
        req = self._req()
        req.COOKIES[FIRST_TOUCH_COOKIE] = 'eyJiIjogImFpIn0:forged'
        self.assertEqual(first_touch_for_signup(req)['bucket'], 'direct')


class RegistrationEventFirstTouchTest(TestCase):
    """creator_registered carries the first touch as $set_once person properties."""

    def test_set_once_block_without_raw_url(self):
        """
        GIVEN a registration request carrying a first-touch cookie
        WHEN the user_registered signal fires
        THEN creator_registered is emitted with $set_once first-touch properties
             and no raw referrer URL
        """
        rf = _AIRequestFactory()
        req = rf.get('/accounts/register/')
        req.session = {}
        req.COOKIES[FIRST_TOUCH_COOKIE] = encode_first_touch(
            {'r': 'https://duckduckgo.com/?q=map+survey', 'h': 'duckduckgo.com',
             'b': 'search_other', 's': '', 'm': '', 'c': '', 'p': '/', 't': 1},
        )
        user = User.objects.create_user('ft_signal', password='x')
        with _ai_patch('survey.signals.pe.emit') as emit:
            _user_registered.send(sender=self.__class__, user=user, request=req)
        calls = [c for c in emit.call_args_list if c.args[0] == _pe.CREATOR_REGISTERED]
        self.assertEqual(len(calls), 1)
        props = calls[0].args[2]
        once = props['$set_once']
        self.assertEqual(once['first_source_bucket'], 'search_other')
        self.assertEqual(once['first_referrer_host'], 'duckduckgo.com')
        self.assertEqual(once['first_landing_path'], '/')
        self.assertNotIn('?q=', str(props))


class ReclassifyAttributionCommandTest(TestCase):
    """sync_posthog_person_properties --reclassify repairs stored buckets."""

    def test_internal_referrer_and_ai_utm_are_repaired(self):
        """
        GIVEN a row spoiled by the internal referrer and a row from ChatGPT stored as other
        WHEN the command runs with --reclassify --dry-run
        THEN the first becomes direct and the second becomes ai, with nothing sent
        """
        from io import StringIO
        from django.core.management import call_command

        u1 = User.objects.create_user('rc_internal', password='x')
        _SA.objects.create(user=u1, raw_referrer='https://mapsurvey.org/', source_bucket='other')
        u2 = User.objects.create_user('rc_chatgpt', password='x')
        _SA.objects.create(user=u2, raw_referrer='', source_bucket='other', utm_source='chatgpt.com')

        out = StringIO()
        call_command('sync_posthog_person_properties', '--reclassify', '--dry-run', stdout=out)
        self.assertEqual(_SA.objects.get(user=u1).source_bucket, 'direct')
        self.assertEqual(_SA.objects.get(user=u2).source_bucket, 'ai')
        self.assertIn('reclassified: 2', out.getvalue())
