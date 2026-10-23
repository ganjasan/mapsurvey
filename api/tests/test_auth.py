"""`api-authentication`: bearer only, uniform refusal, principal, last use, envelope, log hygiene."""
from datetime import timedelta
from unittest import mock

from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from survey import product_events as pe

from .. import auth, limits, tokens
from ..decorators import api_endpoint
from ..models import AUDIENCE_API, AUDIENCE_MCP, TokenProfile
from .helpers import LOCMEM, bearer, make_org, mint

_real_save = TokenProfile.save

ME = reverse('api_me')


@LOCMEM
class BearerOnlyTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.value, self.profile = mint(self.owner)

    def test_session_cookie_without_bearer_is_401(self):
        """
        GIVEN a signed-in browser session and no Authorization header
        WHEN /api/v1/me is requested
        THEN 401 invalid_token with WWW-Authenticate, whatever the cookie says
        """
        self.client.login(username=self.owner.username, password='pass')
        response = self.client.get(ME)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')
        # The REST API adds its RFC 9728 metadata URL to the challenge (#380).
        self.assertTrue(response['WWW-Authenticate'].startswith('Bearer realm="mapsurvey"'))
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_query_string_token_is_401(self):
        """
        GIVEN the token in the query string only
        WHEN /me is requested
        THEN 401
        """
        response = self.client.get(ME + f'?access_token={self.value}')
        self.assertEqual(response.status_code, 401)

    def test_cross_site_form_post_with_cookies_changes_nothing(self):
        """
        GIVEN a signed-in browser posting an HTML form to an API path (no bearer)
        WHEN the request arrives
        THEN 401 -- the CSRF check is skipped because the cookie is not a credential here
        """
        self.client.login(username=self.owner.username, password='pass')
        response = self.client.post(ME, {'x': '1'}, HTTP_ORIGIN='https://evil.example')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')

    def test_valid_bearer_resolves(self):
        """
        GIVEN a valid personal token
        WHEN /me is requested with it
        THEN 200 and the principal describes the token
        """
        response = self.client.get(ME, **bearer(self.value))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['token']['kind'], 'personal')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_bearer_header_shapes(self):
        """
        GIVEN headers that are not `Bearer <value>`
        WHEN parsed
        THEN they are treated as no bearer at all
        """
        rf = RequestFactory()
        self.assertIsNone(auth.bearer_value(rf.get('/')))
        self.assertIsNone(auth.bearer_value(rf.get('/', HTTP_AUTHORIZATION='Basic abc')))
        self.assertIsNone(auth.bearer_value(rf.get('/', HTTP_AUTHORIZATION='Bearer')))
        self.assertEqual(auth.bearer_value(rf.get('/', HTTP_AUTHORIZATION='bearer  x ')), 'x')


@LOCMEM
class UniformRefusalTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.value, self.profile = mint(self.owner)

    def _body(self, value):
        response = self.client.get(ME, **bearer(value))
        self.assertEqual(response.status_code, 401)
        return response.json()

    def test_revoked_expired_inactive_wrong_audience_identical(self):
        """
        GIVEN revoked, expired, deactivated-user, wrong-audience and unknown tokens
        WHEN each is presented
        THEN every body is the same 401 invalid_token
        """
        unknown = self._body('msk_' + 'a' * 43)

        tokens.revoke(self.profile)
        self.assertEqual(self._body(self.value), unknown)

        v2, p2 = mint(self.owner, expires=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self._body(v2), unknown)

        v3, _ = mint(self.owner, audiences=(AUDIENCE_MCP,))
        self.assertEqual(self._body(v3), unknown)

        v4, _ = mint(self.owner)
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self._body(v4), unknown)

    def test_deactivation_takes_effect_on_the_next_call(self):
        """
        GIVEN a token that just worked
        WHEN its user is deactivated between two calls
        THEN the second call is 401 with no caching window
        """
        self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 200)
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 401)

    def test_malformed_values_make_no_token_query(self):
        """
        GIVEN oversized, prefix-less and empty bearer values
        WHEN presented
        THEN 401 and no database query for a token row
        """
        for bad in ('x' * 10000, 'abc', 'msk_short', 'msk_' + 'y' * 300, 'msr_' + 'r' * 43, 'msa_short'):
            with self.assertNumQueries(0):
                response = self.client.get(ME, **bearer(bad))
            self.assertEqual(response.status_code, 401, bad)
            self.assertEqual(response.json()['error'], 'invalid_token')

    def test_oauth_prefix_is_looked_up(self):
        """
        GIVEN a well-formed msa_ value with no row behind it
        WHEN presented
        THEN it reaches the lookup (one query) and is still 401 -- the shape is ours, the row is not
        """
        from .. import tokens
        self.assertTrue(tokens.looks_like_token('msa_' + 'a' * 43))
        self.assertFalse(tokens.looks_like_token('msr_' + 'a' * 43))
        response = self.client.get(ME, **bearer('msa_' + 'a' * 43))
        self.assertEqual(response.status_code, 401)

    def test_oauth_row_without_profile_is_refused(self):
        """
        GIVEN an access-token row with no TokenProfile (not minted by us)
        WHEN presented
        THEN 401
        """
        from oauth2_provider.models import AccessToken, set_token_value
        raw = 'msk_' + 'z' * 43
        row = AccessToken(user=self.owner, scope='surveys:read', expires=timezone.now() + timedelta(days=1))
        set_token_value(row, raw)
        row.save()
        self.assertEqual(self.client.get(ME, **bearer(raw)).status_code, 401)


@LOCMEM
class PrincipalAndLastUseTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.value, self.profile = mint(self.owner, scopes_=('surveys:read',))

    def test_principal_fields(self):
        """
        GIVEN a valid token with one scope
        WHEN authenticate() runs
        THEN the Principal carries the user, the scope set, no binding, the id and the kind
        """
        request = RequestFactory().get('/', **bearer(self.value))
        p = auth.authenticate(request, AUDIENCE_API)
        self.assertEqual(p.user, self.owner)
        self.assertEqual(p.scopes, frozenset({'surveys:read'}))
        self.assertIsNone(p.organization)
        self.assertEqual(p.token_id, self.profile.token_id)
        self.assertEqual(p.kind, 'personal')
        self.assertTrue(p.has_scope('surveys:read'))
        self.assertFalse(p.has_scope('surveys:write'))

    def test_no_bearer_is_none(self):
        """
        GIVEN no Authorization header
        WHEN authenticate() runs
        THEN None, no exception
        """
        self.assertIsNone(auth.authenticate(RequestFactory().get('/'), AUDIENCE_API))

    def test_last_used_written_once_per_minute_and_first_use_once(self):
        """
        GIVEN 100 calls within seconds
        WHEN they authenticate
        THEN last_used_at is written once and api_token_first_use is emitted once
        """
        rf = RequestFactory()
        with mock.patch('survey.product_events.emit') as emit, \
                mock.patch.object(TokenProfile, 'save', autospec=True, side_effect=_real_save) as save:
            for _ in range(100):
                auth.authenticate(rf.get('/', **bearer(self.value)), AUDIENCE_API)
        self.assertEqual(save.call_count, 1)
        self.assertEqual([c.args[0] for c in emit.call_args_list], [pe.API_TOKEN_FIRST_USE])
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.last_used_at)

    def test_last_used_refreshes_after_a_minute(self):
        """
        GIVEN a token last used two minutes ago
        WHEN it authenticates again
        THEN last_used_at moves and no second first-use event fires
        """
        self.profile.last_used_at = timezone.now() - timedelta(minutes=2)
        self.profile.save(update_fields=['last_used_at'])
        before = self.profile.last_used_at
        with mock.patch('survey.product_events.emit') as emit:
            auth.authenticate(RequestFactory().get('/', **bearer(self.value)), AUDIENCE_API)
        self.profile.refresh_from_db()
        self.assertGreater(self.profile.last_used_at, before)
        emit.assert_not_called()


@LOCMEM
class EnvelopeTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.value, self.profile = mint(self.owner)

    def test_unhandled_exception_is_the_envelope(self):
        """
        GIVEN an API view that raises
        WHEN called with a valid bearer
        THEN 500 {"error": "server_error"} with no-store and no traceback
        """
        @api_endpoint(AUDIENCE_API)
        def boom(request):
            raise RuntimeError('secret model detail ' + self.value)

        with mock.patch('api.decorators.logger'):
            response = boom(RequestFactory().get('/api/v1/boom', **bearer(self.value)))
        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        self.assertIn('"server_error"', body)
        self.assertNotIn('RuntimeError', body)
        self.assertNotIn(self.value, body)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_dict_return_becomes_json(self):
        """
        GIVEN a view returning a dict
        WHEN called
        THEN it is JSON with no-store
        """
        @api_endpoint(AUDIENCE_API)
        def ok(request):
            return {'ok': True}

        response = ok(RequestFactory().get('/api/v1/ok', **bearer(self.value)))
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_exception_capture_carries_no_token(self):
        """
        GIVEN PostHog enabled and a view that raises while the request carries a bearer
        WHEN the decorator hands the exception to PostHog
        THEN nothing passed to capture_exception contains the token value
        """
        import posthog

        @api_endpoint(AUDIENCE_API)
        def boom(request):
            raise RuntimeError('boom')

        with mock.patch.object(posthog, 'disabled', False, create=True), \
                mock.patch.object(posthog, 'capture_exception', create=True) as cap, \
                mock.patch('survey.product_events.emit'), \
                mock.patch('api.decorators.logger'):
            boom(RequestFactory().get('/api/v1/boom', **bearer(self.value)))
        self.assertEqual(cap.call_count, 1)
        self.assertNotIn(self.value, repr(cap.call_args))


class ScrubTest(TestCase):
    def test_api_path_tags_keep_only_path_and_method(self):
        """
        GIVEN SDK tags for an /api/ request that somehow include header-shaped tags
        WHEN the scrubber runs
        THEN only $request_path and $request_method survive
        """
        from mapsurvey.settings import _posthog_scrub_tags
        tags = {
            '$request_path': '/api/v1/me', '$request_method': 'GET', '$current_url': 'https://x/api/v1/me',
            '$ip_address': '1.2.3.4', '$user_agent': 'curl', 'Authorization': 'Bearer msk_abc',
            '$request_headers': {'Authorization': 'Bearer msk_abc'}, 'email': 'a@b.c',
        }
        out = _posthog_scrub_tags(dict(tags))
        self.assertEqual(out, {'$request_path': '/api/v1/me', '$request_method': 'GET'})

    def test_header_tags_dropped_everywhere(self):
        """
        GIVEN an editor-path event with a header-shaped tag
        WHEN scrubbed
        THEN the header tag is gone and the rest stays
        """
        from mapsurvey.settings import _posthog_scrub_tags
        out = _posthog_scrub_tags({'$request_path': '/editor/', 'email': 'a@b.c', 'http_cookie': 'sid=1',
                                   'authorization_header': 'Bearer x'})
        self.assertEqual(out, {'$request_path': '/editor/', 'email': 'a@b.c'})
