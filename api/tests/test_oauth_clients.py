"""Client registration (spec oauth-client-registration, change oauth-server, #313):
the redirect rule on every path, DCR with its abuse controls, CIMD through the
toolkit's fetcher, first-party rows, the purge.
"""
import io
import json
import socket
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from oauth2_provider.cimd import CIMDError, SafeMetadataFetcher
from oauth2_provider.models import AccessToken, Application, RefreshToken

from ..oauth import redirects
from ..oauth.cimd import MetadataFetcher
from ..oauth.dcr import clean_name, normalise_metadata
from .helpers import (
    AUTHORIZE, LOCMEM, ME, REGISTER, authorize_params, bearer, consent, exchange, grant, make_app, make_pro_org,
    oauth_settings, pkce, query,
)

OAUTH = oauth_settings()

CLAUDE_CB = 'https://claude.ai/api/mcp/auth_callback'
CHATGPT_CB = 'https://chatgpt.com/connector/oauth/abc123'
CHATGPT_LEGACY_CB = 'https://chatgpt.com/connector_platform_oauth_redirect'


def register(client, **overrides):
    body = {
        'client_name': 'My agent', 'redirect_uris': ['https://app.example/cb'],
        'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token'],
        'response_types': ['code'],
    }
    body.update(overrides)
    return client.post(REGISTER, json.dumps(body), content_type='application/json')


class RedirectRulesTest(TestCase):
    def test_registrable(self):
        """
        GIVEN candidate URIs
        WHEN judged by the one helper
        THEN https and loopback http pass; everything else names its problem
        """
        for ok in ('https://app.example/cb', 'http://127.0.0.1:1/cb', 'http://[::1]:5000/cb',
                   'http://localhost:53124/callback', CLAUDE_CB, CHATGPT_CB, CHATGPT_LEGACY_CB):
            self.assertIsNone(redirects.problem(ok), ok)
        for bad in ('http://example.com/cb', 'http://127.0.0.1.evil.example/cb', 'https://app.example/cb#frag',
                    'https://user@app.example/cb', 'https://*.example/cb', 'ftp://x/y', 'cb', 'myapp://cb'):
            self.assertIsNotNone(redirects.problem(bad), bad)
        with self.assertRaises(ValidationError):
            redirects.check_registrable(['https://ok.example/cb', 'http://example.com/cb'])

    def test_matching(self):
        """
        GIVEN registered URIs
        WHEN a requested URI is matched
        THEN exact for https, any port for loopback, nothing else
        """
        registered = ['https://app.example/cb', 'http://127.0.0.1:1/callback', 'http://localhost:1/callback']
        self.assertTrue(redirects.matches('https://app.example/cb', registered))
        self.assertFalse(redirects.matches('https://app.example:8443/cb', registered))
        self.assertFalse(redirects.matches('https://app.example/cb/', registered))
        self.assertTrue(redirects.matches('http://127.0.0.1:53124/callback', registered))
        self.assertTrue(redirects.matches('http://localhost:53124/callback', registered))
        self.assertFalse(redirects.matches('http://localhost:53124/other', registered))
        self.assertFalse(redirects.matches('http://[::1]:53124/callback', registered), 'host must match too')
        self.assertFalse(redirects.matches('http://example.com/cb', ['http://example.com/cb']),
                         'a non-loopback http URI never matches, even if a row holds it')


@OAUTH
@LOCMEM
class RedirectOnEveryPathTest(TestCase):
    def setUp(self):
        cache.clear()  # the DCR limiter counts per IP; the test client is always one IP
        self.org, self.user = make_pro_org()
        self.client.force_login(self.user)

    def test_loopback_any_port(self):
        """
        GIVEN a client registered with loopback URIs on port 1
        WHEN authorize names port 53124
        THEN the flow completes and the code goes to that port
        """
        app = make_app(name='Claude Code', redirect_uris='http://127.0.0.1:1/callback http://localhost:1/callback',
                       source='dcr')
        verifier, challenge = pkce()
        uri = 'http://localhost:53124/callback'
        page = self.client.get(AUTHORIZE, authorize_params(app, challenge, redirect_uri=uri))
        self.assertEqual(page.status_code, 200)
        response = consent(self.client, page.content.decode())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(uri + '?'), response['Location'])
        token = exchange(self.client, app, query(response['Location'])['code'], verifier, redirect_uri=uri)
        self.assertEqual(token.status_code, 200, token.content)

    def test_non_loopback_http_refused_on_every_path(self):
        """
        GIVEN redirect_uris with http://example.com/cb
        WHEN registered through DCR, through a CIMD document, or saved from the shell/admin
        THEN DCR answers 400 invalid_redirect_uri, CIMD fails, the save raises
        """
        response = register(self.client, redirect_uris=['http://example.com/cb'])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_redirect_uri')
        self.assertEqual(Application.objects.count(), 0)

        doc = {'client_id': 'https://client.example/c.json', 'client_name': 'x',
               'redirect_uris': ['http://example.com/cb'], 'token_endpoint_auth_method': 'none'}
        with mock.patch.object(SafeMetadataFetcher, 'fetch', return_value=(doc, 300)):
            with self.assertRaises(CIMDError):
                MetadataFetcher().fetch('https://client.example/c.json')

        with self.assertRaises(ValidationError):
            make_app(redirect_uris='http://example.com/cb')

    def test_known_callbacks_register(self):
        """
        GIVEN the documented claude.ai and ChatGPT callbacks
        WHEN registered through DCR
        THEN each registers and matches exactly
        """
        for cb in (CLAUDE_CB, CHATGPT_CB, CHATGPT_LEGACY_CB):
            response = register(self.client, redirect_uris=[cb])
            self.assertEqual(response.status_code, 201, response.content)
            app = Application.objects.get(client_id=response.json()['client_id'])
            self.assertTrue(redirects.matches(cb, app.redirect_uris.split()))
            self.assertFalse(redirects.matches(cb + 'x', app.redirect_uris.split()))


@OAUTH
@LOCMEM
class DcrTest(TestCase):
    def setUp(self):
        cache.clear()  # the limiter counts per IP; the test client is always one IP

    def test_registration(self):
        """
        GIVEN an anonymous JSON registration of a public client
        WHEN posted
        THEN 201 with client_id and registration_access_token; the row is public with that redirect URI
        """
        response = register(self.client)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertIn('client_id', data)
        self.assertIn('registration_access_token', data)
        self.assertEqual(data['token_endpoint_auth_method'], 'none')
        app = Application.objects.get(client_id=data['client_id'])
        self.assertEqual(app.client_type, Application.CLIENT_PUBLIC)
        self.assertEqual(app.redirect_uris, 'https://app.example/cb')
        self.assertEqual(app.registration_source, Application.RegistrationSource.DCR)
        self.assertEqual(app.name, 'My agent')

    def test_extension_grant_is_ignored(self):
        """
        GIVEN a registration that also lists the jwt-bearer extension grant (#404)
        WHEN posted
        THEN 201, and the registered grant types are only the two this server issues
        """
        response = register(self.client, grant_types=[
            'authorization_code', 'refresh_token', 'urn:ietf:params:oauth:grant-type:jwt-bearer'])
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(sorted(response.json()['grant_types']), ['authorization_code', 'refresh_token'])

    def test_eleventh_registration_in_an_hour_is_429(self):
        """
        GIVEN ten registrations from one IP
        WHEN the eleventh arrives
        THEN 429 with Retry-After and no new row
        """
        for i in range(10):
            self.assertEqual(register(self.client, client_name=f'agent {i}').status_code, 201)
        response = register(self.client, client_name='one too many')
        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.has_header('Retry-After'))
        self.assertEqual(response.json()['error'], 'rate_limited')
        self.assertEqual(Application.objects.count(), 10)

    def test_long_name_is_cut(self):
        """
        GIVEN client_name of 10 000 characters
        WHEN registered
        THEN 201 and the stored name is 80 characters
        """
        response = register(self.client, client_name='N' * 10_000)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(Application.objects.get().name), 80)

    def test_name_normalisation(self):
        """
        GIVEN a name with control characters and runs of whitespace
        WHEN cleaned
        THEN they are gone
        """
        self.assertEqual(clean_name('  Map\u0000survey\n\n  Official\t'), 'Mapsurvey Official')
        self.assertEqual(clean_name(None), '')

    def test_logo_is_dropped_and_never_fetched(self):
        """
        GIVEN a registration with logo_uri
        WHEN registered and the consent page renders
        THEN no outbound request, no logo stored, no <img> on the page
        """
        with mock.patch('urllib3.HTTPSConnectionPool') as pool, mock.patch('socket.getaddrinfo') as dns:
            response = register(self.client, logo_uri='https://tracker.example/pixel.png',
                                client_uri='https://tracker.example/')
            pool.assert_not_called()
            dns.assert_not_called()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('logo_uri', response.json())
        out = normalise_metadata({'client_name': 'x', 'logo_uri': 'https://t/p.png', 'tos_uri': 'https://t/tos'})
        self.assertEqual(set(out), {'client_name'})

    def test_registration_token_on_the_api(self):
        """
        GIVEN the RFC 7592 registration token
        WHEN presented as a bearer to /api/v1/me
        THEN 401 invalid_token
        """
        token = register(self.client).json()['registration_access_token']
        response = self.client.get(ME, **bearer(token))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')

    def test_rfc7592_read_update_delete(self):
        """
        GIVEN a registered client with its registration token
        WHEN it GETs, PUTs normalised metadata and DELETEs its configuration
        THEN each works and the PUT applies the redirect rule
        """
        data = register(self.client).json()
        url = f"{REGISTER}{data['client_id']}/"
        auth = bearer(data['registration_access_token'])
        self.assertEqual(self.client.get(url, **auth).status_code, 200)

        bad = self.client.put(url, json.dumps({'client_name': 'x', 'redirect_uris': ['http://example.com/cb'],
                                                'token_endpoint_auth_method': 'none'}),
                              content_type='application/json', **auth)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()['error'], 'invalid_redirect_uri')

        good = self.client.put(url, json.dumps({'client_name': 'R' * 500, 'redirect_uris': [CLAUDE_CB],
                                                 'token_endpoint_auth_method': 'none',
                                                 'grant_types': ['authorization_code', 'refresh_token']}),
                               content_type='application/json', **auth)
        self.assertEqual(good.status_code, 200, good.content)
        app = Application.objects.get(client_id=data['client_id'])
        self.assertEqual(len(app.name), 80)
        self.assertEqual(app.redirect_uris, CLAUDE_CB)

        auth2 = bearer(good.json().get('registration_access_token', data['registration_access_token']))
        self.assertEqual(self.client.delete(url, **auth2).status_code, 204)
        self.assertFalse(Application.objects.filter(client_id=data['client_id']).exists())

    def test_malformed_body_is_the_toolkits_400(self):
        """
        GIVEN a body that is not JSON
        WHEN posted
        THEN 400 from the toolkit, nothing created
        """
        response = self.client.post(REGISTER, 'not json', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Application.objects.count(), 0)


class _Response:
    def __init__(self, status=200, body=b'{}', content_type='application/json', cache_control=None):
        self.status = status
        self._body = io.BytesIO(body)
        self.headers = {'Content-Type': content_type}
        if cache_control:
            self.headers['Cache-Control'] = cache_control

    def read(self, n=-1):
        return self._body.read(n)


@OAUTH
@LOCMEM
class CimdTest(TestCase):
    URL = 'https://client.example/.well-known/client.json'

    def setUp(self):
        cache.clear()  # the toolkit backs off a failing client_id URL for 60 s -- per test, not per class
        self.org, self.user = make_pro_org()
        self.client.force_login(self.user)

    def _authorize(self, client_id, redirect_uri=CLAUDE_CB):
        _, challenge = pkce()
        params = {'response_type': 'code', 'client_id': client_id, 'redirect_uri': redirect_uri,
                  'scope': 'surveys:read', 'state': 's', 'code_challenge': challenge,
                  'code_challenge_method': 'S256'}
        return self.client.get(AUTHORIZE, params)

    def _assert_invalid_client(self, response):
        """A failed resolution looks like an unknown client to the flow: oauthlib's
        InvalidClientIdError (code `invalid_request`, "Invalid client_id parameter
        value."), rendered as a page -- never a redirect."""
        html = response.content.decode()
        self.assertEqual(response.status_code, 400, html[html.find('oa-error'):][:400])
        self.assertFalse(response.has_header('Location'))
        self.assertIn('Invalid client_id', html)
        self.assertNotIn('authorizationForm', html)

    def test_private_address(self):
        """
        GIVEN client_id on a private IP literal
        WHEN authorize is requested
        THEN no connection is attempted and the page says invalid_client
        """
        with mock.patch('urllib3.HTTPSConnectionPool') as pool:
            response = self._authorize('https://10.0.0.5/client.json')
            pool.assert_not_called()
        self._assert_invalid_client(response)

    def test_host_resolving_to_the_metadata_address(self):
        """
        GIVEN a host that resolves to 169.254.169.254
        WHEN authorize is requested
        THEN no connection, invalid_client
        """
        info = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('169.254.169.254', 443))]
        with mock.patch('socket.getaddrinfo', return_value=info), mock.patch('urllib3.HTTPSConnectionPool') as pool:
            response = self._authorize('https://meta.example/client.json')
            pool.assert_not_called()
        self._assert_invalid_client(response)

    def test_http_scheme(self):
        """
        GIVEN client_id over http
        WHEN authorize is requested
        THEN invalid_client
        """
        with mock.patch('urllib3.HTTPSConnectionPool') as pool:
            response = self._authorize('http://client.example/client.json')
            pool.assert_not_called()
        self._assert_invalid_client(response)

    def test_redirecting_document(self):
        """
        GIVEN the document URL answers 302
        WHEN read
        THEN the redirect is not followed and the fetch fails
        """
        with self.assertRaises(CIMDError):
            MetadataFetcher()._read_document(_Response(status=302))

    def test_oversized_document(self):
        """
        GIVEN a 1 MB document
        WHEN read
        THEN reading stops at the cap and the fetch fails
        """
        with self.assertRaises(CIMDError):
            MetadataFetcher()._read_document(_Response(body=b'{"a":"' + b'x' * (1024 * 1024) + b'"}'))

    def test_mismatching_client_id(self):
        """
        GIVEN a document whose client_id differs from the URL
        WHEN authorize is requested
        THEN invalid_client
        """
        doc = {'client_id': 'https://other.example/c.json', 'client_name': 'x', 'redirect_uris': [CLAUDE_CB],
               'token_endpoint_auth_method': 'none'}
        with mock.patch.object(SafeMetadataFetcher, 'fetch', return_value=(doc, 300)):
            response = self._authorize(self.URL)
        self._assert_invalid_client(response)
        self.assertFalse(Application.objects.filter(client_id=self.URL).exists())

    def test_valid_document(self):
        """
        GIVEN a valid document for a claude.ai-style client
        WHEN authorize is requested and the user allows
        THEN consent shows the client host and the flow completes with an oauth token
        """
        doc = {'client_id': self.URL, 'client_name': 'Claude', 'redirect_uris': [CLAUDE_CB],
               'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token'],
               'response_types': ['code'], 'logo_uri': 'https://client.example/logo.png'}
        with mock.patch.object(SafeMetadataFetcher, 'fetch', return_value=(doc, 300)):
            page = self._authorize(self.URL)
            html = page.content.decode()
            self.assertEqual(page.status_code, 200, html[html.find('oa-error'):][:600])
            html = page.content.decode()
            self.assertIn('class="oa-host">client.example<', html)
            self.assertNotIn('logo.png', html)
            response = consent(self.client, html)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].startswith(CLAUDE_CB))
        app = Application.objects.get(client_id=self.URL)
        self.assertEqual(app.registration_source, Application.RegistrationSource.CIMD)
        self.assertEqual(app.name, 'Claude')

    def test_claude_ai_document_with_jwt_bearer(self):
        """
        GIVEN claude.ai's real metadata document (2026-10-24), which also lists the
              jwt-bearer extension grant the toolkit cannot store (#404)
        WHEN authorize is requested with that client_id
        THEN the extra grant is ignored, a public authorization-code application exists
             and the consent page renders with claude.ai as the host
        """
        url = 'https://claude.ai/oauth/mcp-oauth-client-metadata'
        doc = {'client_id': url, 'client_name': 'Claude', 'client_uri': 'https://claude.ai',
               'redirect_uris': [CLAUDE_CB],
               'grant_types': ['authorization_code', 'refresh_token',
                               'urn:ietf:params:oauth:grant-type:jwt-bearer'],
               'response_types': ['code'], 'token_endpoint_auth_method': 'none'}
        with mock.patch.object(SafeMetadataFetcher, 'fetch', return_value=(doc, 300)):
            page = self._authorize(url)
        html = page.content.decode()
        self.assertEqual(page.status_code, 200, html[html.find('oa-error'):][:600])
        self.assertIn('class="oa-host">claude.ai<', html)
        app = Application.objects.get(client_id=url)
        self.assertEqual(app.authorization_grant_type, Application.GRANT_AUTHORIZATION_CODE)
        self.assertEqual(app.client_type, Application.CLIENT_PUBLIC)

    def test_document_with_no_supported_grant_is_refused(self):
        """
        GIVEN a document that declares only client_credentials
        WHEN authorize is requested
        THEN it is still the unknown-client page and no application is created
        """
        doc = {'client_id': self.URL, 'client_name': 'x', 'redirect_uris': [CLAUDE_CB],
               'grant_types': ['client_credentials'], 'token_endpoint_auth_method': 'none'}
        with mock.patch.object(SafeMetadataFetcher, 'fetch', return_value=(doc, 300)):
            response = self._authorize(self.URL)
        self._assert_invalid_client(response)
        self.assertFalse(Application.objects.filter(client_id=self.URL).exists())


@OAUTH
class FirstPartyTest(TestCase):
    def test_skip_consent(self):
        """
        GIVEN a manual application with skip_authorization
        WHEN a signed-in user opens a valid authorize URL
        THEN a code redirect without a page
        """
        org, user = make_pro_org()
        self.client.force_login(user)
        app = make_app(name='Mapsurvey CLI', skip=True)
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(app, challenge))
        self.assertEqual(response.status_code, 302)
        self.assertIn('code', query(response['Location']))

    def test_admin_lists_applications(self):
        """
        GIVEN a staff user
        WHEN the application changelist renders
        THEN registration source and counts are columns
        """
        from django.contrib.auth.models import User
        staff = User.objects.create_superuser('staff', 'staff@example.test', 'pass')
        make_app(source='dcr')
        self.client.force_login(staff)
        response = self.client.get('/admin/oauth2_provider/application/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Dynamic Client Registration', response.content.decode())


@OAUTH
class PurgeTest(TestCase):
    def _old(self, app, days=31):
        Application.objects.filter(pk=app.pk).update(created=timezone.now() - timedelta(days=days))

    def test_stale_registration_is_deleted(self):
        """
        GIVEN a DCR application 31 days old, never authorised, with only its registration token
        WHEN purge_oauth_clients runs
        THEN it and its token are gone
        """
        app = make_app(source='dcr')
        AccessToken.objects.create(application=app, user=None, scope='oauth2_provider:registration',
                                   expires=timezone.now() + timedelta(days=3650), token='reg-token-value')
        self._old(app)
        out = io.StringIO()
        call_command('purge_oauth_clients', stdout=out)
        self.assertIn('1 stale', out.getvalue())
        self.assertFalse(Application.objects.filter(pk=app.pk).exists())
        self.assertEqual(AccessToken.objects.count(), 0)

    def test_live_and_manual_registrations_stay(self):
        """
        GIVEN an old DCR application with a live refresh token, an old manual one, and a young DCR one
        WHEN the command runs
        THEN none is deleted
        """
        org, user = make_pro_org()
        self.client.force_login(user)
        live = make_app(name='live', source='dcr')
        grant(self.client, live)
        self.assertTrue(RefreshToken.objects.filter(application=live, revoked__isnull=True).exists())
        manual = make_app(name='manual', source='manual')
        young = make_app(name='young', source='dcr')
        self._old(live)
        self._old(manual, days=400)
        call_command('purge_oauth_clients', stdout=io.StringIO())
        self.assertEqual(set(Application.objects.values_list('name', flat=True)), {'live', 'manual', 'young'})
