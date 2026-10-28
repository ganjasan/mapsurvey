"""Tests for the `survey-embedding` capability (openspec/specs/survey-embedding/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, Client, override_settings
from io import BytesIO
import re
from survey.models import SurveyHeader, SurveySession, Answer, SurveyCollaborator
from survey.serialization import serialize_survey_to_dict, export_survey_to_zip, import_survey_from_zip
from survey.models import SurveyEvent
from django.test import RequestFactory
from django.conf import settings
from survey.embedding import normalise_allowed_hosts, frame_ancestors, InvalidHost
from urllib.parse import urlencode
from survey.tests.helpers import _EmbedSurveyMixin


class AllowedHostsParsingTest(SimpleTestCase):

    def test_hosts_are_tidied_and_deduplicated(self):
        """
        GIVEN a textarea with a pasted URL, a wildcard, blanks and a duplicate
        WHEN it is normalised
        THEN scheme, path and case are dropped and each host appears once, in order
        """
        text = 'https://City.Example.org/projects\n*.consult.example\n\ncity.example.org, EXAMPLE.COM:8443/'
        self.assertEqual(
            normalise_allowed_hosts(text),
            ['city.example.org', '*.consult.example', 'example.com'],
        )

    def test_invalid_entry_is_named(self):
        """
        GIVEN an entry that is not a host name
        WHEN it is normalised
        THEN InvalidHost carries that entry
        """
        with self.assertRaises(InvalidHost) as ctx:
            normalise_allowed_hosts('city.example.org\nnot a host')
        self.assertEqual(str(ctx.exception), 'not a host')
        for bad in ('*', '*.', 'a.*.b', '-bad.example', 'héllo.exam ple'):
            with self.assertRaises(InvalidHost):
                normalise_allowed_hosts(bad)

    def test_idna_hosts_are_encoded(self):
        """
        GIVEN a Unicode host name
        WHEN it is normalised
        THEN it is stored in its IDNA form
        """
        self.assertEqual(normalise_allowed_hosts('Мэрия.рф'), ['xn--h1ahm5cm.xn--p1ai'])

    def test_frame_ancestors_rendering(self):
        """
        GIVEN an empty list and a list with a wildcard host
        WHEN rendered as a frame-ancestors directive
        THEN the empty list means any site and the list keeps 'self' first
        """
        self.assertEqual(frame_ancestors([]), '*')
        self.assertEqual(
            frame_ancestors(['city.example.org', '*.consult.example']),
            "'self' https://city.example.org https://*.consult.example",
        )


class EmbedFramingHeadersTest(_EmbedSurveyMixin, TestCase):

    def test_published_survey_without_allowlist_is_framable_anywhere(self):
        """
        GIVEN a published survey with an empty allow-list
        WHEN its entry URL, a section and the thanks page are requested anonymously
        THEN each response allows any frame ancestor and carries no X-Frame-Options
        """
        survey = self._make_embed_survey()
        for path in (f'/surveys/{survey.uuid}/', f'/surveys/{survey.uuid}/sec1/', f'/surveys/{survey.uuid}/thanks/'):
            response = self.client.get(path)
            self.assertEqual(response['Content-Security-Policy'], 'frame-ancestors *', path)
            self.assertFalse(response.has_header('X-Frame-Options'), path)

    def test_allowlist_restricts_ancestors(self):
        """
        GIVEN a published survey allowing two hosts
        WHEN its first section is requested
        THEN the directive lists 'self' and the two https origins
        """
        survey = self._make_embed_survey(embed_allowed_hosts=['city.example.org', '*.consult.example'])
        response = self.client.get(f'/surveys/{survey.uuid}/sec1/')
        self.assertEqual(
            response['Content-Security-Policy'],
            "frame-ancestors 'self' https://city.example.org https://*.consult.example",
        )

    def test_allowlist_is_read_from_the_canonical_row(self):
        """
        GIVEN a published survey with an allow-list and an archived version of it
        WHEN the archived version's UUID is requested
        THEN the canonical survey's allow-list is applied
        """
        survey = self._make_embed_survey(embed_allowed_hosts=['city.example.org'])
        old = SurveyHeader.objects.create(
            name='embed_old', organization=self.org, created_by=self.owner, status='archived',
            is_canonical=False, canonical_survey=survey, embed_allowed_hosts=['other.example'],
        )
        response = self.client.get(f'/surveys/{old.uuid}/')
        self.assertEqual(response['Content-Security-Policy'], "frame-ancestors 'self' https://city.example.org")

    def test_editor_and_landing_stay_unframeable(self):
        """
        GIVEN the landing page and the editor
        WHEN they are requested
        THEN they keep X-Frame-Options: SAMEORIGIN and no frame-ancestors directive
        """
        survey = self._make_embed_survey()
        self.client.login(username='embed_owner', password='pass')
        for path in ('/', f'/editor/surveys/{survey.uuid}/'):
            response = self.client.get(path)
            self.assertEqual(response.get('X-Frame-Options'), 'SAMEORIGIN', path)
            self.assertNotIn('frame-ancestors', response.get('Content-Security-Policy', ''), path)

    def test_draft_stays_unframeable(self):
        """
        GIVEN a draft survey
        WHEN an anonymous visitor requests it
        THEN the 404 keeps X-Frame-Options: SAMEORIGIN
        """
        survey = self._make_embed_survey(status='draft')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertFalse(response.has_header('Content-Security-Policy'))

    def test_closed_survey_page_is_framable(self):
        """
        GIVEN a closed survey
        WHEN an anonymous visitor requests it
        THEN the closed page allows framing (a host page should show the notice, not a blank box)
        """
        survey = self._make_embed_survey(status='closed')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response['Content-Security-Policy'], 'frame-ancestors *')
        self.assertFalse(response.has_header('X-Frame-Options'))


class CrossSiteCookiesTest(_EmbedSurveyMixin, TestCase):

    def test_switch_is_off_by_default(self):
        """
        GIVEN no CROSS_SITE_COOKIES in the environment
        WHEN settings load
        THEN the switch is off, because on it cost nine days of answers from the
             Facebook and Instagram in-app browsers on iOS (#388)
        """
        from django.conf import settings as dj_conf
        self.assertFalse(dj_conf.CROSS_SITE_COOKIES)

    @override_settings(CROSS_SITE_COOKIES=True,
                       SESSION_COOKIE_SAMESITE='None', SESSION_COOKIE_SECURE=True,
                       CSRF_COOKIE_SAMESITE='None', CSRF_COOKIE_SECURE=True)
    def test_cookies_carry_cross_site_attributes(self):
        """
        GIVEN CROSS_SITE_COOKIES settings in force
        WHEN a respondent opens a survey section
        THEN sessionid and csrftoken are SameSite=None, Secure and Partitioned
        """
        survey = self._make_embed_survey()
        response = self.client.get(f'/surveys/{survey.uuid}/sec1/', secure=True)
        for name in ('sessionid', 'csrftoken'):
            header = response.cookies[name].output(header='')
            self.assertIn('SameSite=None', header, name)
            self.assertIn('Secure', header, name)
            self.assertIn('Partitioned', header, name)

    @override_settings(SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=False,
                       CSRF_COOKIE_SAMESITE='Lax', CSRF_COOKIE_SECURE=False)
    def test_cookies_keep_defaults_when_switch_is_off(self):
        """
        GIVEN the default (local HTTP) cookie settings
        WHEN a respondent opens a survey section
        THEN sessionid is SameSite=Lax with neither Secure nor Partitioned
        """
        survey = self._make_embed_survey()
        response = self.client.get(f'/surveys/{survey.uuid}/sec1/')
        header = response.cookies['sessionid'].output(header='')
        self.assertIn('SameSite=Lax', header)
        self.assertNotIn('Partitioned', header)
        self.assertNotIn('Secure', header)

    @override_settings(SESSION_COOKIE_SAMESITE='None', SESSION_COOKIE_SECURE=True,
                       CSRF_COOKIE_SAMESITE='None', CSRF_COOKIE_SECURE=True)
    def test_cross_site_forgery_is_still_rejected(self):
        """
        GIVEN a respondent with a valid session and CSRF cookie
        WHEN a section POST arrives with an Origin naming another site
        THEN the CSRF middleware answers 403
        """
        survey = self._make_embed_survey()
        client = Client(enforce_csrf_checks=True)
        client.get(f'/surveys/{survey.uuid}/sec1/', secure=True)
        token = client.cookies['csrftoken'].value
        response = client.post(
            f'/surveys/{survey.uuid}/sec1/', {'Q1': 'Blue', 'csrfmiddlewaretoken': token},
            secure=True, HTTP_ORIGIN='https://evil.example',
        )
        self.assertEqual(response.status_code, 403)


@override_settings(CROSS_SITE_COOKIES=False)
class StalePartitionedCookieTest(_EmbedSurveyMixin, TestCase):
    """The clean-up after nine days of `Partitioned` cookies (change cross-site-cookies-off).

    A browser that took the partitioned `csrftoken`/`sessionid` between 13 and
    22 October 2026 keeps them next to the plain ones and sends both; Django
    reads the last, the editor's JavaScript reads the first, and every JSON
    POST fails CSRF. Only the raw Cookie header shows the duplicate.
    """

    @staticmethod
    def _run(cookie_header, set_on_response=None):
        """The middleware around a bare response: what a JSON endpoint sends back."""
        from django.http import HttpResponse
        from django.test import RequestFactory
        from survey.middleware import PartitionedCookieMiddleware

        def view(request):
            response = HttpResponse('{}', content_type='application/json')
            for name, value in (set_on_response or {}).items():
                response.set_cookie(name, value)
            return response

        request = RequestFactory().get('/editor/whats-new/cards/', HTTP_COOKIE=cookie_header)
        return PartitionedCookieMiddleware(view)(request)

    @staticmethod
    def _deletion(response, name):
        header = response.cookies[name].output(header='')
        return ('Max-Age=0' in header and 'Partitioned' in header
                and 'SameSite=None' in header and 'Secure' in header)

    def test_duplicate_csrftoken_is_swept(self):
        """
        GIVEN a request whose Cookie header carries csrftoken twice
        WHEN the response sets no csrftoken itself
        THEN it deletes the partitioned variant: Max-Age=0 with the attributes that match it
        """
        response = self._run('csrftoken=aaa; csrftoken=aaa')
        self.assertTrue(self._deletion(response, 'csrftoken'))
        self.assertNotIn('sessionid', response.cookies)

    def test_duplicate_sessionid_is_swept(self):
        """
        GIVEN a request whose Cookie header carries sessionid twice
        WHEN the response sets no sessionid itself
        THEN it deletes the partitioned sessionid the same way
        """
        response = self._run('sessionid=k1; sessionid=k2')
        self.assertTrue(self._deletion(response, 'sessionid'))

    def test_single_cookies_cost_nothing(self):
        """
        GIVEN a request with one csrftoken and one sessionid
        WHEN the response sets neither
        THEN no deletion is sent, so every ordinary visitor is untouched
        """
        response = self._run('csrftoken=aaa; sessionid=k1')
        self.assertEqual(list(response.cookies), [])

    def test_response_already_setting_the_cookie_wins(self):
        """
        GIVEN a duplicate csrftoken
        WHEN the view's response already sets csrftoken
        THEN the middleware leaves that Set-Cookie as it is: one per name, the
             deletion waits for a later response
        """
        response = self._run('csrftoken=aaa; csrftoken=aaa', {'csrftoken': 'fresh'})
        self.assertEqual(response.cookies['csrftoken'].value, 'fresh')
        self.assertFalse(self._deletion(response, 'csrftoken'))

    def test_response_setting_the_cookie_is_left_alone(self):
        """
        GIVEN the same duplicate on a survey section page
        WHEN Django sets csrftoken on that response with the value it read
        THEN the response keeps that cookie and carries no deletion, so one
             Set-Cookie per name is never fought over
        """
        survey = self._make_embed_survey()
        response = self.client.get(f'/surveys/{survey.uuid}/sec1/', HTTP_COOKIE='csrftoken=aaa; csrftoken=aaa')
        self.assertEqual(response.status_code, 200)
        header = response.cookies['csrftoken'].output(header='')
        self.assertNotIn('Max-Age=0', header)
        self.assertNotIn('Partitioned', header)

    def test_sweep_is_off_while_the_switch_is_on(self):
        """
        GIVEN CROSS_SITE_COOKIES on
        WHEN a duplicate arrives
        THEN nothing is deleted — the partitioned cookie is the one in use then
        """
        with override_settings(CROSS_SITE_COOKIES=True):
            response = self._run('csrftoken=aaa; csrftoken=aaa')
        self.assertEqual(list(response.cookies), [])


class EmbeddedSessionMetadataTest(_EmbedSurveyMixin, TestCase):

    def _session_start(self, survey):
        session = SurveySession.objects.filter(survey=survey).latest('id')
        return SurveyEvent.objects.get(session=session, event_type='session_start').metadata

    def test_frame_load_from_another_site(self):
        """
        GIVEN a request that is a cross-site frame navigation with a Referer
        WHEN a session starts
        THEN its metadata says embedded with the embedding host, www-stripped and lower-cased
        """
        survey = self._make_embed_survey()
        self.client.get(
            f'/surveys/{survey.uuid}/sec1/',
            HTTP_SEC_FETCH_DEST='iframe', HTTP_SEC_FETCH_SITE='cross-site',
            HTTP_REFERER='https://www.City.example.org/projects/park',
        )
        meta = self._session_start(survey)
        self.assertTrue(meta['embedded'])
        self.assertEqual(meta['embed_host'], 'city.example.org')

    def test_embed_flag_in_query_counts(self):
        """
        GIVEN a browser that sends no Fetch Metadata
        WHEN the snippet URL with embed=1 starts a session
        THEN the session is marked embedded
        """
        survey = self._make_embed_survey()
        self.client.get(f'/surveys/{survey.uuid}/sec1/?embed=1')
        self.assertTrue(self._session_start(survey)['embedded'])

    def test_plain_link_is_not_embedded(self):
        """
        GIVEN a top-level navigation
        WHEN a session starts
        THEN embedded is False and embed_host empty
        """
        survey = self._make_embed_survey()
        self.client.get(f'/surveys/{survey.uuid}/sec1/', HTTP_SEC_FETCH_DEST='document', HTTP_SEC_FETCH_SITE='none')
        meta = self._session_start(survey)
        self.assertFalse(meta['embedded'])
        self.assertEqual(meta['embed_host'], '')

    def test_live_preview_is_not_an_embed(self):
        """
        GIVEN the editor's same-origin preview frame
        WHEN a session starts
        THEN it is not marked embedded
        """
        survey = self._make_embed_survey()
        self.client.get(f'/surveys/{survey.uuid}/sec1/', HTTP_SEC_FETCH_DEST='iframe', HTTP_SEC_FETCH_SITE='same-origin')
        self.assertFalse(self._session_start(survey)['embedded'])


class FramedCompletionTest(_EmbedSurveyMixin, TestCase):

    def _finish(self, survey, **extra):
        self.client.get(f'/surveys/{survey.uuid}/sec1/')
        self.client.post(f'/surveys/{survey.uuid}/sec1/', {'Q1': 'Blue'}, HTTP_HX_REQUEST='true', **extra)
        return self.client.post(f'/surveys/{survey.uuid}/sec2/', {'Q2': 'Berlin'}, HTTP_HX_REQUEST='true', **extra)

    def test_framed_submit_lands_on_thanks_with_next(self):
        """
        GIVEN a survey with a custom redirect_url
        WHEN the last section is submitted via HTMX from a framed page
        THEN HX-Redirect points at the thanks page carrying next=<redirect_url>
        """
        survey = self._make_embed_survey(redirect_url='https://example.com/thanks')
        response = self._finish(survey, HTTP_MS_EMBEDDED='1')
        self.assertEqual(
            response['HX-Redirect'],
            f'/surveys/{survey.uuid}/thanks/?next=https%3A%2F%2Fexample.com%2Fthanks',
        )

    def test_top_level_submit_is_unchanged(self):
        """
        GIVEN the same survey
        WHEN the last section is submitted without the framed header
        THEN HX-Redirect is the redirect_url itself
        """
        survey = self._make_embed_survey(redirect_url='https://example.com/thanks')
        response = self._finish(survey)
        self.assertEqual(response['HX-Redirect'], 'https://example.com/thanks')

    def test_framed_submit_without_redirect_goes_to_plain_thanks(self):
        """
        GIVEN a survey with the built-in thanks page
        WHEN the last section is submitted from a framed page
        THEN HX-Redirect is the thanks page with no next parameter
        """
        survey = self._make_embed_survey()
        response = self._finish(survey, HTTP_MS_EMBEDDED='1')
        self.assertEqual(response['HX-Redirect'], f'/surveys/{survey.uuid}/thanks/')

    def test_thanks_page_offers_the_continue_link(self):
        """
        GIVEN a survey whose redirect_url is https://example.com/thanks
        WHEN its thanks page is requested with next equal to that URL
        THEN the page links to it with target="_top"
        """
        survey = self._make_embed_survey(redirect_url='https://example.com/thanks')
        response = self.client.get(f'/surveys/{survey.uuid}/thanks/?next=https://example.com/thanks')
        self.assertContains(response, 'href="https://example.com/thanks" target="_top"')

    def test_forged_next_is_ignored(self):
        """
        GIVEN the same survey
        WHEN the thanks page is requested with a next naming another site
        THEN no link to that site is rendered
        """
        survey = self._make_embed_survey(redirect_url='https://example.com/thanks')
        response = self.client.get(f'/surveys/{survey.uuid}/thanks/?next=https://evil.example/')
        self.assertNotContains(response, 'evil.example')
        self.assertNotContains(response, 'target="_top"')


class CarriedSessionTest(_EmbedSurveyMixin, TestCase):
    """Safari/iOS keep no cookies in a third-party frame: the page carries its session."""

    FRAMED = {'HTTP_SEC_FETCH_DEST': 'iframe', 'HTTP_SEC_FETCH_SITE': 'cross-site'}
    ORIGIN = {'HTTP_ORIGIN': 'http://testserver'}

    @staticmethod
    def _carried(body):
        key = re.search(r'name="ms-embed-session" content="([a-z0-9]{32})"', body)
        field = re.search(r'name="ms_sid" value="([a-z0-9]{32})"', body)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)
        return (key or field).group(1) if (key or field) else None, token.group(1) if token else None

    def _framed_first_section(self, survey):
        """A framed first-section load by a browser that will drop the cookies."""
        page = Client(enforce_csrf_checks=True).get(f'/surveys/{survey.uuid}/sec1/', **self.FRAMED)
        key, token = self._carried(page.content.decode())
        self.assertTrue(key, 'framed page carries no session key')
        self.assertTrue(token)
        return key, token

    def test_section_submitted_from_a_frame_without_cookies(self):
        """
        GIVEN a browser that stored nothing from the framed first section
        WHEN it submits the section via HTMX with the carried key and the page's CSRF token
        THEN the answer lands in the session the first section created and section two comes back
        """
        survey = self._make_embed_survey()
        key, token = self._framed_first_section(survey)
        cookieless = Client(enforce_csrf_checks=True)
        response = cookieless.post(
            f'/surveys/{survey.uuid}/sec1/', {'Q1': 'Blue', 'csrfmiddlewaretoken': token},
            HTTP_X_MS_SESSION=key, HTTP_HX_REQUEST='true', **self.ORIGIN,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Two')
        self.assertTrue(response.wsgi_request.ms_session_carried)
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        from importlib import import_module
        store = import_module(settings.SESSION_ENGINE).SessionStore(key)
        answer = Answer.objects.get(survey_session_id=store['survey_session_id'], question__code='Q1')
        self.assertEqual(answer.text, 'Blue')

    def test_carried_request_without_csrf_token_is_refused(self):
        """
        GIVEN the same carried key
        WHEN the submit arrives without the CSRF token
        THEN CSRF protection still answers 403
        """
        survey = self._make_embed_survey()
        key, _ = self._framed_first_section(survey)
        response = Client(enforce_csrf_checks=True).post(
            f'/surveys/{survey.uuid}/sec1/', {'Q1': 'Blue'},
            HTTP_X_MS_SESSION=key, HTTP_HX_REQUEST='true', **self.ORIGIN,
        )
        self.assertEqual(response.status_code, 403)

    def test_a_signed_in_session_cannot_be_carried(self):
        """
        GIVEN the session key of a signed-in creator
        WHEN an anonymous request carries it to a draft survey
        THEN the key is ignored: no editor bypass, the draft is a 404
        """
        survey = self._make_embed_survey(status='draft')
        creator = Client()
        creator.login(username='embed_owner', password='pass')
        key = creator.session.session_key
        response = Client().get(f'/surveys/{survey.uuid}/sec1/', HTTP_X_MS_SESSION=key, **self.FRAMED)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.wsgi_request.ms_session_carried)

    def test_handoff_on_the_final_redirect(self):
        """
        GIVEN a cookie-less respondent on the last section
        WHEN they submit it
        THEN HX-Redirect carries a one-time handoff, following it completes that session, and the token is spent
        """
        survey = self._make_embed_survey()
        key, token = self._framed_first_section(survey)
        cookieless = Client(enforce_csrf_checks=True)
        cookieless.post(f'/surveys/{survey.uuid}/sec1/', {'Q1': 'Blue', 'csrfmiddlewaretoken': token},
                        HTTP_X_MS_SESSION=key, HTTP_HX_REQUEST='true', **self.ORIGIN)
        final = cookieless.post(f'/surveys/{survey.uuid}/sec2/', {'Q2': 'Berlin', 'csrfmiddlewaretoken': token},
                                HTTP_X_MS_SESSION=key, HTTP_HX_REQUEST='true', **self.ORIGIN)
        target = final['HX-Redirect']
        self.assertIn(f'/surveys/{survey.uuid}/thanks/?ms_h=', target)
        self.assertNotIn(key, target)

        thanks = Client().get(target)
        self.assertEqual(thanks.status_code, 200)
        self.assertTrue(thanks.wsgi_request.ms_session_carried)
        session = SurveySession.objects.get(survey=survey)
        self.assertTrue(SurveyEvent.objects.filter(session=session, event_type='survey_complete').exists())
        self.assertEqual(Answer.objects.filter(survey_session=session).count(), 2)

        again = Client().get(target)
        self.assertEqual(again.status_code, 200)
        self.assertFalse(again.wsgi_request.ms_session_carried)

    def test_language_picker_without_cookies(self):
        """
        GIVEN a framed multilingual survey
        WHEN the language form is posted with the carried field and a same-host Origin
        THEN the redirect carries a handoff and the chosen language is in that session
        """
        survey = self._make_embed_survey(available_languages=['en', 'ru'])
        page = Client(enforce_csrf_checks=True).get(f'/surveys/{survey.uuid}/language/', **self.FRAMED)
        key, token = self._carried(page.content.decode())
        self.assertTrue(key)
        response = Client(enforce_csrf_checks=True).post(
            f'/surveys/{survey.uuid}/language/',
            urlencode({'language': 'ru', 'csrfmiddlewaretoken': token, 'ms_sid': key}),
            content_type='application/x-www-form-urlencoded', **self.ORIGIN,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/sec1/?ms_h=', response['Location'])
        section = Client().get(response['Location'])
        self.assertEqual(section.status_code, 200)
        self.assertTrue(section.wsgi_request.ms_session_carried)
        self.assertEqual(section.wsgi_request.session.get('survey_language'), 'ru')

    def test_form_field_from_a_foreign_origin_is_ignored(self):
        """
        GIVEN a carried key in the form field but an Origin naming another site
        WHEN the language form is posted
        THEN the key is not adopted and CSRF refuses the request
        """
        survey = self._make_embed_survey(available_languages=['en', 'ru'])
        page = Client(enforce_csrf_checks=True).get(f'/surveys/{survey.uuid}/language/', **self.FRAMED)
        key, token = self._carried(page.content.decode())
        response = Client(enforce_csrf_checks=True).post(
            f'/surveys/{survey.uuid}/language/',
            urlencode({'language': 'ru', 'csrfmiddlewaretoken': token, 'ms_sid': key}),
            content_type='application/x-www-form-urlencoded', HTTP_ORIGIN='https://evil.example',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.wsgi_request.ms_session_carried)

    def test_cookie_wins_over_a_carried_key(self):
        """
        GIVEN a respondent whose cookies work
        WHEN a request also names another session in the header
        THEN the cookie session is used and nothing is carried
        """
        survey = self._make_embed_survey()
        other_key, _ = self._framed_first_section(survey)
        with_cookies = Client()
        with_cookies.get(f'/surveys/{survey.uuid}/sec1/')
        own_key = with_cookies.session.session_key
        response = with_cookies.get(f'/surveys/{survey.uuid}/sec1/', HTTP_X_MS_SESSION=other_key, **self.FRAMED)
        self.assertEqual(response.wsgi_request.session.session_key, own_key)
        self.assertFalse(response.wsgi_request.ms_session_carried)

    def test_top_level_respondents_are_unchanged(self):
        """
        GIVEN a respondent outside any frame
        WHEN they load a section and finish the survey
        THEN the page carries no session meta and the final redirect carries no handoff
        """
        survey = self._make_embed_survey()
        self.client.get(f'/surveys/{survey.uuid}/sec1/')
        page = self.client.get(f'/surveys/{survey.uuid}/sec1/')
        self.assertNotContains(page, '<meta name="ms-embed-session"')
        self.client.post(f'/surveys/{survey.uuid}/sec1/', {'Q1': 'Blue'}, HTTP_HX_REQUEST='true')
        final = self.client.post(f'/surveys/{survey.uuid}/sec2/', {'Q2': 'Berlin'}, HTTP_HX_REQUEST='true')
        self.assertEqual(final['HX-Redirect'], f'/surveys/{survey.uuid}/thanks/')


class SharePageEmbedTest(_EmbedSurveyMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.client.login(username='embed_owner', password='pass')

    def test_snippet_is_shown_for_a_published_survey(self):
        """
        GIVEN a published survey
        WHEN its owner opens the Share page
        THEN the iframe snippet with embed=1, geolocation allowance, embed.js and the embed_copied capture are present
        """
        survey = self._make_embed_survey()
        response = self.client.get(f'/editor/surveys/{survey.uuid}/share/')
        self.assertContains(response, f'/surveys/{survey.uuid}/?embed=1')
        self.assertContains(response, 'allow=&quot;geolocation; fullscreen&quot;')
        self.assertContains(response, '/embed.js')
        self.assertContains(response, "trackShare('embed_copied')")

    def test_snippet_uses_the_public_scheme_behind_the_proxy(self):
        """
        GIVEN a request that reached us over https through a proxy (X-Forwarded-Proto)
        WHEN the owner opens the Share page
        THEN the snippet, embed.js and the survey link all say https://, never the proxy's http
        """
        survey = self._make_embed_survey()
        response = self.client.get(f'/editor/surveys/{survey.uuid}/share/', HTTP_X_FORWARDED_PROTO='https')
        body = response.content.decode()
        self.assertIn(f'https://testserver/surveys/{survey.uuid}/?embed=1', body)
        self.assertIn('https://testserver/embed.js', body)
        self.assertIn(f'value="https://testserver/surveys/{survey.uuid}/"', body)
        self.assertNotIn('http://testserver', body)

    def test_snippet_is_withheld_until_published(self):
        """
        GIVEN a testing survey
        WHEN its owner opens the Share page
        THEN no embed snippet is rendered
        """
        survey = self._make_embed_survey(status='testing')
        response = self.client.get(f'/editor/surveys/{survey.uuid}/share/')
        self.assertNotContains(response, 'embed=1')

    def test_allowed_hosts_are_normalised_and_saved(self):
        """
        GIVEN a published survey
        WHEN the owner saves a messy allowed-hosts list
        THEN the canonical row stores the tidied list and the page confirms the save
        """
        survey = self._make_embed_survey()
        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/share/embed/',
            {'allowed_hosts': 'https://City.Example.org/projects\n*.consult.example\n\ncity.example.org'},
        )
        self.assertEqual(response.status_code, 302)
        survey.refresh_from_db()
        self.assertEqual(survey.embed_allowed_hosts, ['city.example.org', '*.consult.example'])

    def test_invalid_host_is_rejected(self):
        """
        GIVEN a survey with a saved allow-list
        WHEN the owner submits an entry that is not a host
        THEN the page shows the error and the stored list is unchanged
        """
        survey = self._make_embed_survey(embed_allowed_hosts=['city.example.org'])
        response = self.client.post(f'/editor/surveys/{survey.uuid}/share/embed/', {'allowed_hosts': 'not a host'})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'is not a host name', status_code=400)
        survey.refresh_from_db()
        self.assertEqual(survey.embed_allowed_hosts, ['city.example.org'])

    def test_hosts_saved_from_a_draft_copy_land_on_the_canonical(self):
        """
        GIVEN a published survey with an open draft copy
        WHEN the owner saves allowed hosts from the draft copy's Share page
        THEN the published survey stores them
        """
        survey = self._make_embed_survey()
        draft = SurveyHeader.objects.create(
            name='[draft] embed', organization=self.org, created_by=self.owner,
            status='draft', published_version=survey,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=draft, role='owner')
        self.client.post(f'/editor/surveys/{draft.uuid}/share/embed/', {'allowed_hosts': 'city.example.org'})
        survey.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(survey.embed_allowed_hosts, ['city.example.org'])
        self.assertEqual(draft.embed_allowed_hosts, [])

    def test_allowed_hosts_round_trip_through_export(self):
        """
        GIVEN a survey with an allow-list
        WHEN it is exported and imported, and when an archive without the key is imported
        THEN the list survives and the old archive imports as an empty list
        """
        survey = self._make_embed_survey(embed_allowed_hosts=['city.example.org'])
        buf = BytesIO()
        export_survey_to_zip(survey, buf, mode='structure')
        buf.seek(0)
        imported, _ = import_survey_from_zip(buf, organization=self.org, created_by=self.owner)
        self.assertEqual(imported.embed_allowed_hosts, ['city.example.org'])

        data = serialize_survey_to_dict(survey)
        del data['embed_allowed_hosts']
        from survey.serialization import _clean_embed_hosts
        self.assertEqual(_clean_embed_hosts(data.get('embed_allowed_hosts')), [])

    def test_embed_js_is_served_at_a_stable_path(self):
        """
        GIVEN the helper script in the static assets
        WHEN /embed.js is requested
        THEN it is served as JavaScript with a public cache header
        """
        for _ in range(2):  # the second request serves the cached body
            response = self.client.get('/embed.js')
            self.assertEqual(response.status_code, 200)
            self.assertIn('javascript', response['Content-Type'])
            self.assertIn('public', response['Cache-Control'])
            self.assertIn('mapsurvey', response.content.decode())
