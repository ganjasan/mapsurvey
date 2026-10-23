"""The authorization server (spec oauth-authorization-server, change oauth-server, #313).

Every method name here is a line of the issue's security checklist. The flows
drive the real endpoints with the test client -- login, authorize, consent,
token -- and never mock oauthlib.
"""
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken, Grant, RefreshToken

from survey import product_events as pe
from survey.models import AuditLog, Membership

from ..models import TokenProfile
from ..oauth.validator import code_checksum
from .helpers import (
    AUTHORIZE, LOCMEM, ME, METADATA, RESOURCES, REVOKE, TOKEN, authorize_params, bearer, consent, exchange,
    form_fields, grant, make_app, make_free_org, make_pro_org, make_user, oauth_settings, pkce, query, refresh,
)

OAUTH = oauth_settings()


class _Flow(TestCase):
    def setUp(self):
        self.org, self.user = make_pro_org()
        self.app = make_app()
        self.client.force_login(self.user)


@OAUTH
class MetadataTest(TestCase):
    def test_required_members_and_the_pkce_list(self):
        """
        GIVEN the server
        WHEN a client GETs the RFC 8414 document
        THEN the required members are there, S256 is the only PKCE method and every URL starts with the issuer
        """
        data = self.client.get(METADATA).json()
        self.assertEqual(data['issuer'], 'https://testserver')
        self.assertEqual(data['code_challenge_methods_supported'], ['S256'])
        self.assertEqual(data['response_types_supported'], ['code'])
        self.assertEqual(data['grant_types_supported'], ['authorization_code', 'refresh_token'])
        self.assertIn('none', data['token_endpoint_auth_methods_supported'])
        self.assertTrue(data['client_id_metadata_document_supported'])
        self.assertTrue(data['authorization_response_iss_parameter_supported'])
        for key in ('authorization_endpoint', 'token_endpoint', 'revocation_endpoint', 'registration_endpoint'):
            self.assertTrue(data[key].startswith('https://testserver/oauth/'), (key, data[key]))
        self.assertEqual(data['authorization_endpoint'], 'https://testserver/oauth/authorize/')
        self.assertEqual(data['revocation_endpoint'], 'https://testserver/oauth/revoke/')
        from .. import scopes
        self.assertEqual(data['scopes_supported'], sorted(scopes.SCOPES))
        for absent in ('introspection_endpoint', 'jwks_uri', 'userinfo_endpoint'):
            self.assertNotIn(absent, data)

    def test_preview_issues_for_itself(self):
        """
        GIVEN a Render preview (IS_PULL_REQUEST=true, its own external hostname) with SITE_URL = production
        WHEN settings are evaluated
        THEN OAUTH_ISSUER is the preview host, not production
        """
        import importlib
        import os
        env = {'IS_PULL_REQUEST': 'true', 'RENDER_EXTERNAL_HOSTNAME': 'mapsurvey-pr-1.onrender.com',
               'SITE_URL': 'https://mapsurvey.org'}
        with mock.patch.dict(os.environ, env):
            from mapsurvey import settings as module
            fresh = importlib.reload(module)
            issuer = fresh.OAUTH_ISSUER
            resources = dict(fresh.API_RESOURCE_URLS)
        importlib.reload(module)  # restore the process's settings module
        self.assertEqual(issuer, 'https://mapsurvey-pr-1.onrender.com')
        self.assertEqual(resources['api'], 'https://mapsurvey-pr-1.onrender.com/api/')

    def test_unmounted_routes(self):
        """
        GIVEN the hand-built URL list
        WHEN the toolkit's other routes are requested
        THEN each is 404
        """
        for path in ('/oauth/introspect/', '/oauth/applications/', '/oauth/device/',
                     '/.well-known/openid-configuration', '/oauth/.well-known/oauth-authorization-server',
                     '/.well-known/oauth-protected-resource'):
            self.assertEqual(self.client.get(path).status_code, 404, path)


@OAUTH
class AuthorizeTest(_Flow):
    def test_anonymous_visitor_is_sent_to_login_with_next(self):
        """
        GIVEN no session
        WHEN a valid authorize URL is opened
        THEN the response redirects to login and next is the authorize URL with its query
        """
        self.client.logout()
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertIn('code_challenge', response['Location'])
        self.assertIn('next=', response['Location'])

    def test_missing_code_challenge_redirects_with_error_and_state(self):
        """
        GIVEN a signed-in user
        WHEN the authorize URL has no code_challenge
        THEN the response redirects to the registered URI with error=invalid_request and the state
        """
        params = authorize_params(self.app, 'x', state='s1')
        del params['code_challenge']
        del params['code_challenge_method']
        response = self.client.get(AUTHORIZE, params)
        self.assertEqual(response.status_code, 302)
        q = query(response['Location'])
        self.assertTrue(response['Location'].startswith('https://app.example/cb'))
        self.assertEqual(q['error'], 'invalid_request')
        self.assertEqual(q['state'], 's1')
        self.assertEqual(Grant.objects.count(), 0)

    def test_plain_method_is_refused(self):
        """
        GIVEN code_challenge_method=plain
        WHEN authorize is requested
        THEN it is refused with invalid_request and no code is issued
        """
        _, challenge = pkce()
        params = authorize_params(self.app, challenge, code_challenge_method='plain')
        response = self.client.get(AUTHORIZE, params)
        if response.status_code == 200:  # the page rendered: Allow must still refuse
            response = consent(self.client, response.content.decode())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(query(response['Location']).get('error'), 'invalid_request')
        self.assertEqual(Grant.objects.count(), 0)

    def test_unregistered_redirect_uri_is_a_page_not_a_redirect(self):
        """
        GIVEN a registered client
        WHEN redirect_uri is one it did not register
        THEN the response is an error page with no Location header and no consent form
        """
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge,
                                                               redirect_uri='https://evil.example/cb'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.has_header('Location'))
        html = response.content.decode()
        self.assertNotIn('authorizationForm', html)
        self.assertIn('cannot connect', html)

    def test_different_port_on_a_non_loopback_host_is_refused(self):
        """
        GIVEN https://app.example/cb registered
        WHEN https://app.example:8443/cb is requested
        THEN an error page, no Location
        """
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge,
                                                               redirect_uri='https://app.example:8443/cb'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.has_header('Location'))

    def test_state_too_long_is_a_page(self):
        """
        GIVEN state of 513 bytes
        WHEN authorize is requested
        THEN an error page naming invalid_request, no Location
        """
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, state='s' * 513))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.has_header('Location'))
        self.assertIn('invalid_request', response.content.decode())

    def test_state_round_trips_byte_for_byte(self):
        """
        GIVEN a 512-byte state full of URL-unsafe characters
        WHEN the user allows
        THEN the state on the redirect is exactly the value sent
        """
        state = 'a&b=c d/é?#%' * 50
        while len(state.encode('utf-8')) > 512:
            state = state[:-1]
        self.assertEqual(len(state.encode('utf-8')), 512)
        verifier, challenge = pkce()
        page = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, state=state))
        self.assertEqual(page.status_code, 200)
        response = consent(self.client, page.content.decode())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(query(response['Location'])['state'], state)

    def test_unknown_resource_is_invalid_target(self):
        """
        GIVEN resource=https://evil.example/
        WHEN authorize is requested
        THEN redirect to the registered URI with error=invalid_target and the state
        """
        _, challenge = pkce()
        params = authorize_params(self.app, challenge, state='s2', resource='https://evil.example/')
        response = self.client.get(AUTHORIZE, params)
        self.assertEqual(response.status_code, 302)
        q = query(response['Location'])
        self.assertEqual(q['error'], 'invalid_target')
        self.assertEqual(q['state'], 's2')

    def test_inactive_account_gets_no_code(self):
        """
        GIVEN the signed-in user is deactivated
        WHEN authorize is requested
        THEN no code is issued and no consent form is rendered
        """
        self.user.is_active = False
        self.user.save()
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge))
        self.assertNotIn('authorizationForm', response.content.decode())
        self.assertEqual(Grant.objects.count(), 0)
        if response.status_code == 302:
            self.assertNotIn('code=', response['Location'])


@OAUTH
class ConsentTest(_Flow):
    def test_attacker_chosen_name_shows_the_host_first(self):
        """
        GIVEN a DCR client named "Mapsurvey Official" redirecting to evil.example
        WHEN consent renders
        THEN evil.example appears before the name, in the host slot
        """
        app = make_app(name='Mapsurvey Official', redirect_uris='https://evil.example/cb', source='dcr')
        _, challenge = pkce()
        html = self.client.get(AUTHORIZE, authorize_params(app, challenge)).content.decode()
        self.assertIn('class="oa-host">evil.example<', html)
        self.assertLess(html.index('evil.example'), html.index('Mapsurvey Official'))
        self.assertNotIn('<img', html.split('authorizationForm')[0])

    def test_dangerous_scopes_are_switches_off_by_default(self):
        """
        GIVEN a request for read, write and publish
        WHEN the page renders and the user allows without ticking
        THEN read and write are granted, publish is an unchecked switch and the code's scope lacks it
        """
        verifier, challenge = pkce()
        page = self.client.get(AUTHORIZE, authorize_params(self.app, challenge,
                                                           scope='surveys:read surveys:write surveys:publish'))
        html = page.content.decode()
        self.assertIn('name="switch_surveys_publish"', html)
        self.assertNotIn('name="switch_surveys_publish" checked', html)
        self.assertNotIn('switch_surveys_delete', html)
        response = consent(self.client, html)
        token = exchange(self.client, self.app, query(response['Location'])['code'], verifier).json()
        self.assertEqual(token['scope'], 'surveys:read surveys:write')

    def test_switch_ticked_grants_the_scope(self):
        """
        GIVEN publish requested
        WHEN the user ticks the switch
        THEN the token carries surveys:publish
        """
        token = grant(self.client, self.app, scope='surveys:read surveys:publish', switches=('surveys:publish',))
        self.assertEqual(token['scope'], 'surveys:read surveys:publish')

    def test_scope_cannot_be_added(self):
        """
        GIVEN the client requested surveys:read only
        WHEN the form is posted with a ticked delete switch and an edited hidden scope
        THEN the issued scope is surveys:read
        """
        verifier, challenge = pkce()
        page = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, scope='surveys:read'))
        data = form_fields(page.content.decode())
        data['scope'] = 'surveys:read surveys:delete'
        data['switch_surveys_delete'] = 'on'
        data['allow'] = '1'
        response = self.client.post(AUTHORIZE, data)
        self.assertEqual(response.status_code, 302)
        token = exchange(self.client, self.app, query(response['Location'])['code'], verifier).json()
        self.assertEqual(token['scope'], 'surveys:read')

    def test_free_workspace_note_and_pro_required_after(self):
        """
        GIVEN a user whose only workspace is Free
        WHEN they allow
        THEN the page carried the note, the code is issued and /api/v1/me reports api false
        """
        org, user = make_free_org()
        self.client.force_login(user)
        _, challenge = pkce()
        html = self.client.get(AUTHORIZE, authorize_params(self.app, challenge)).content.decode()
        self.assertIn('pro_required', html)
        self.assertIn('Free', html)
        token = grant(self.client, self.app)
        me = self.client.get(ME, **bearer(token['access_token'])).json()
        self.assertEqual([w['api'] for w in me['workspaces']], [False])

    def test_page_lists_workspaces_with_plans(self):
        """
        GIVEN memberships in a Pro and a Free workspace
        WHEN the page renders
        THEN both names and plans are shown and there is no Free note
        """
        free, _ = make_free_org('Second Org', 'second_owner')
        Membership.objects.create(user=self.user, organization=free, role='editor')
        _, challenge = pkce()
        html = self.client.get(AUTHORIZE, authorize_params(self.app, challenge)).content.decode()
        self.assertIn('Pro Org', html)
        self.assertIn('Second Org', html)
        self.assertNotIn('pro_required', html)

    def test_cancel(self):
        """
        GIVEN the consent page
        WHEN the user presses Cancel
        THEN redirect with error=access_denied and the state, and no grant row
        """
        _, challenge = pkce()
        page = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, state='keep-me'))
        response = consent(self.client, page.content.decode(), allow=False)
        self.assertEqual(response.status_code, 302)
        q = query(response['Location'])
        self.assertEqual(q['error'], 'access_denied')
        self.assertEqual(q['state'], 'keep-me')
        self.assertEqual(Grant.objects.count(), 0)
        self.assertEqual(AuditLog.objects.filter(action='oauth_consent').count(), 0)

    def test_audit_and_event_on_consent(self):
        """
        GIVEN the user allows
        WHEN the code redirect is issued
        THEN one oauth_consent audit row names the application and scopes and holds no code or token
        """
        with mock.patch('survey.product_events.emit') as emit:
            token = grant(self.client, self.app, scope='surveys:read responses:read')
        row = AuditLog.objects.get(action='oauth_consent')
        self.assertEqual(row.metadata['application_id'], self.app.pk)
        self.assertEqual(row.metadata['scopes'], ['surveys:read', 'responses:read'])
        self.assertEqual(row.metadata['audiences'], ['api', 'mcp'])
        self.assertNotIn(token['access_token'], repr(row.metadata))
        events = [c.args[0] for c in emit.call_args_list]
        self.assertIn(pe.OAUTH_APP_CONNECTED, events)
        props = [c.args[2] for c in emit.call_args_list if c.args[0] == pe.OAUTH_APP_CONNECTED][0]
        self.assertEqual(props['remembered'], False)
        self.assertNotIn('name', props)


@OAUTH
class ConsentMemoryTest(_Flow):
    def test_second_authorize_skips_the_page(self):
        """
        GIVEN a user who allowed surveys:read for a client
        WHEN the same client asks for surveys:read again
        THEN the response is the code redirect without a page
        """
        grant(self.client, self.app)
        _, challenge = pkce()
        with mock.patch('survey.product_events.emit') as emit:
            response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, state='again'))
        self.assertEqual(response.status_code, 302)
        q = query(response['Location'])
        self.assertIn('code', q)
        self.assertEqual(q['state'], 'again')
        props = [c.args[2] for c in emit.call_args_list if c.args[0] == pe.OAUTH_APP_CONNECTED][0]
        self.assertTrue(props['remembered'])

    def test_more_scopes_re_prompt(self):
        """
        GIVEN a remembered grant for surveys:read
        WHEN the client asks for surveys:read responses:read
        THEN the consent page renders
        """
        grant(self.client, self.app)
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge,
                                                               scope='surveys:read responses:read'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('authorizationForm', response.content.decode())

    def test_after_disconnect_re_prompt(self):
        """
        GIVEN a remembered grant
        WHEN the user disconnects the app and authorizes again
        THEN the consent page renders
        """
        grant(self.client, self.app)
        self.client.post('/editor/account/connections/', {'action': 'disconnect', 'application_id': self.app.pk})
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge))
        self.assertEqual(response.status_code, 200)

    def test_first_party_skip_authorization(self):
        """
        GIVEN an application with skip_authorization
        WHEN a signed-in user opens a valid authorize URL
        THEN a code redirect without a page
        """
        app = make_app(name='Mapsurvey CLI', skip=True)
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(app, challenge))
        self.assertEqual(response.status_code, 302)
        self.assertIn('code', query(response['Location']))


@OAUTH
class CodeTest(_Flow):
    def _code(self, **extra):
        verifier, challenge = pkce()
        page = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, **extra))
        response = consent(self.client, page.content.decode())
        return verifier, response

    def test_iss_on_the_redirect(self):
        """
        GIVEN the user allows
        WHEN the redirect is issued
        THEN it carries code, state and iss = issuer
        """
        _, response = self._code(state='s')
        q = query(response['Location'])
        self.assertIn('code', q)
        self.assertEqual(q['state'], 's')
        self.assertEqual(q['iss'], 'https://testserver')

    def test_verifier_mismatch(self):
        """
        GIVEN a code
        WHEN the token request carries a verifier that does not hash to the challenge
        THEN 400 invalid_grant and no access token
        """
        _, response = self._code()
        code = query(response['Location'])['code']
        bad = exchange(self.client, self.app, code, 'not-the-verifier-' + 'x' * 40)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()['error'], 'invalid_grant')
        self.assertEqual(AccessToken.objects.filter(user=self.user).count(), 0)

    def test_redirect_uri_mismatch_at_token(self):
        """
        GIVEN a code bound to the registered URI
        WHEN the token request names another redirect_uri
        THEN it is refused
        """
        verifier, response = self._code()
        code = query(response['Location'])['code']
        bad = exchange(self.client, self.app, code, verifier, redirect_uri='https://app.example/other')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(AccessToken.objects.filter(user=self.user).count(), 0)

    def test_code_used_twice_revokes_the_first_tokens(self):
        """
        GIVEN a code exchanged once
        WHEN it is exchanged again
        THEN the second answer is invalid_grant and the first access and refresh tokens no longer validate
        """
        verifier, response = self._code()
        code = query(response['Location'])['code']
        first = exchange(self.client, self.app, code, verifier).json()
        self.assertEqual(self.client.get(ME, **bearer(first['access_token'])).status_code, 200)
        self.assertEqual(TokenProfile.objects.get(kind='oauth').code_checksum, code_checksum(code))

        second = exchange(self.client, self.app, code, verifier)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()['error'], 'invalid_grant')
        self.assertEqual(self.client.get(ME, **bearer(first['access_token'])).status_code, 401)
        again = refresh(self.client, self.app, first['refresh_token'])
        self.assertEqual(again.status_code, 400)

    def test_code_checksum_follows_the_family(self):
        """
        GIVEN tokens from a code, then one refresh
        WHEN the new access token's profile is read
        THEN it carries the same code checksum, so a late double redemption still finds the family
        """
        verifier, response = self._code()
        code = query(response['Location'])['code']
        first = exchange(self.client, self.app, code, verifier).json()
        second = refresh(self.client, self.app, first['refresh_token']).json()
        profile = AccessToken.objects.get(token_checksum=_checksum(second['access_token'])).profile
        self.assertEqual(profile.code_checksum, code_checksum(code))
        exchange(self.client, self.app, code, verifier)  # replay
        self.assertEqual(self.client.get(ME, **bearer(second['access_token'])).status_code, 401)

    def test_resource_mismatch_between_authorize_and_token(self):
        """
        GIVEN a code issued with resource = api
        WHEN the token request names resource = mcp
        THEN 400 invalid_target
        """
        verifier, response = self._code(resource=RESOURCES['api'])
        code = query(response['Location'])['code']
        bad = exchange(self.client, self.app, code, verifier, resource=RESOURCES['mcp'])
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()['error'], 'invalid_target')

    def test_code_expires_after_ten_minutes(self):
        """
        GIVEN a code
        WHEN it is redeemed after its expiry
        THEN invalid_grant
        """
        verifier, response = self._code()
        code = query(response['Location'])['code']
        g = Grant.objects.get()
        self.assertAlmostEqual((g.expires - timezone.now()).total_seconds(), 600, delta=10)
        g.expires = timezone.now() - timezone.timedelta(seconds=1)
        g.save()
        self.assertEqual(exchange(self.client, self.app, code, verifier).json()['error'], 'invalid_grant')


def _checksum(value):
    import hashlib
    return hashlib.sha256(value.encode()).hexdigest()


@OAUTH
class TokenTest(_Flow):
    def test_successful_exchange(self):
        """
        GIVEN a valid code and verifier
        WHEN posted with client_id
        THEN 200 with a msa_ access token, 3600 s, a msr_ refresh token and scope
        """
        token = grant(self.client, self.app, scope='surveys:read surveys:write')
        self.assertRegex(token['access_token'], r'^msa_[A-Za-z0-9_-]{40,}$')
        self.assertRegex(token['refresh_token'], r'^msr_[A-Za-z0-9_-]{40,}$')
        self.assertEqual(token['token_type'], 'Bearer')
        self.assertEqual(token['expires_in'], 3600)
        self.assertEqual(token['scope'], 'surveys:read surveys:write')
        profile = TokenProfile.objects.get(kind='oauth')
        self.assertEqual(profile.label, 'Test app')
        self.assertEqual(profile.suffix, token['access_token'][-4:])
        self.assertIsNone(profile.organization)
        self.assertFalse(AccessToken.objects.filter(token=token['access_token']).exists(), 'stored hashed')

    def test_audience_from_resource(self):
        """
        GIVEN resource = the API identifier
        WHEN tokens are issued
        THEN audiences == ["api"]; /api/v1/me accepts, authenticate(request, "mcp") refuses
        """
        token = grant(self.client, self.app, resource=RESOURCES['api'])
        self.assertEqual(TokenProfile.objects.get(kind='oauth').audiences, ['api'])
        self.assertEqual(self.client.get(ME, **bearer(token['access_token'])).status_code, 200)
        from django.test import RequestFactory

        from ..auth import authenticate
        from ..errors import ApiError
        request = RequestFactory().get('/mcp/', **bearer(token['access_token']))
        with self.assertRaises(ApiError):
            authenticate(request, 'mcp')

    def test_resource_prefix_match(self):
        """
        GIVEN resource = a URL below the API identifier
        WHEN tokens are issued
        THEN the audience is api
        """
        grant(self.client, self.app, resource=RESOURCES['api'] + 'v1/me')
        self.assertEqual(TokenProfile.objects.get(kind='oauth').audiences, ['api'])

    def test_no_resource_means_both_audiences(self):
        """
        GIVEN no resource anywhere
        WHEN tokens are issued
        THEN audiences are api and mcp
        """
        grant(self.client, self.app)
        self.assertEqual(TokenProfile.objects.get(kind='oauth').audiences, ['api', 'mcp'])

    def test_refresh_rotation_and_reuse(self):
        """
        GIVEN a refresh token used once
        WHEN it is used again
        THEN invalid_grant, and neither token of the new pair validates afterwards
        """
        first = grant(self.client, self.app)
        second = refresh(self.client, self.app, first['refresh_token'])
        self.assertEqual(second.status_code, 200)
        pair = second.json()
        self.assertNotEqual(pair['refresh_token'], first['refresh_token'])
        self.assertEqual(self.client.get(ME, **bearer(pair['access_token'])).status_code, 200)

        replay = refresh(self.client, self.app, first['refresh_token'])
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(replay.json()['error'], 'invalid_grant')
        self.assertEqual(self.client.get(ME, **bearer(pair['access_token'])).status_code, 401)
        self.assertEqual(refresh(self.client, self.app, pair['refresh_token']).status_code, 400)

    def test_refresh_keeps_the_profile(self):
        """
        GIVEN a refresh
        WHEN the new access token is read by authenticate()
        THEN it is an oauth principal with the same scopes and audiences
        """
        first = grant(self.client, self.app, scope='surveys:read responses:read', resource=RESOURCES['api'])
        pair = refresh(self.client, self.app, first['refresh_token']).json()
        me = self.client.get(ME, **bearer(pair['access_token'])).json()
        self.assertEqual(me['token']['kind'], 'oauth')
        self.assertEqual(me['token']['scopes'], ['responses:read', 'surveys:read'])
        self.assertEqual(me['token']['audiences'], ['api'])

    def test_disabled_grants(self):
        """
        GIVEN grant_type client_credentials / password / device
        WHEN posted
        THEN 400 unsupported_grant_type
        """
        for grant_type in ('client_credentials', 'password'):
            response = self.client.post(TOKEN, {'grant_type': grant_type, 'client_id': self.app.client_id,
                                                'username': 'x', 'password': 'y'})
            self.assertEqual(response.status_code, 400, grant_type)
            self.assertEqual(response.json()['error'], 'unsupported_grant_type', grant_type)
        # The toolkit routes the device grant around oauthlib; with no device
        # endpoint mounted no DeviceGrant can exist, so it is an error, not a 500.
        response = self.client.post(TOKEN, {'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                                            'client_id': self.app.client_id, 'device_code': 'x'})
        self.assertGreaterEqual(response.status_code, 400)
        self.assertLess(response.status_code, 500)

    def test_implicit_response_type_is_refused(self):
        """
        GIVEN response_type=token
        WHEN authorize is requested
        THEN it is refused
        """
        _, challenge = pkce()
        response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge, response_type='token'))
        self.assertIn(response.status_code, (302, 400))
        if response.status_code == 302:
            self.assertIn('error=', response['Location'])
            self.assertNotIn('access_token', response['Location'])

    def test_deactivated_user_with_a_live_grant(self):
        """
        GIVEN tokens issued
        WHEN the user is deactivated
        THEN the next call is 401 and the next refresh is refused
        """
        token = grant(self.client, self.app)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.client.get(ME, **bearer(token['access_token'])).status_code, 401)
        self.assertEqual(refresh(self.client, self.app, token['refresh_token']).status_code, 400)


@OAUTH
class RevokeTest(_Flow):
    def test_client_disconnects(self):
        """
        GIVEN a public client with a refresh token
        WHEN it posts the refresh token to /oauth/revoke/ with its client_id
        THEN 200, and both tokens are refused afterwards
        """
        token = grant(self.client, self.app)
        response = self.client.post(REVOKE, {'token': token['refresh_token'], 'client_id': self.app.client_id,
                                             'token_type_hint': 'refresh_token'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(ME, **bearer(token['access_token'])).status_code, 401)
        self.assertEqual(refresh(self.client, self.app, token['refresh_token']).status_code, 400)

    def test_unknown_token_is_200(self):
        """
        GIVEN a value that is no token
        WHEN revoked
        THEN 200 (RFC 7009 §2.2)
        """
        response = self.client.post(REVOKE, {'token': 'msa_nothing', 'client_id': self.app.client_id})
        self.assertEqual(response.status_code, 200)

    def test_revoking_an_access_token(self):
        """
        GIVEN an access token
        WHEN revoked
        THEN authenticate() refuses it
        """
        token = grant(self.client, self.app)
        self.client.post(REVOKE, {'token': token['access_token'], 'client_id': self.app.client_id})
        self.assertEqual(self.client.get(ME, **bearer(token['access_token'])).status_code, 401)


@OAUTH
class HeadersTest(_Flow):
    def test_consent_page_cannot_be_framed(self):
        """
        GIVEN the full middleware stack
        WHEN the consent page renders
        THEN DENY, frame-ancestors 'none', no-store, and the embed mark was never set
        """
        _, challenge = pkce()
        with mock.patch('survey.access_control.mark_embeddable') as mark:
            response = self.client.get(AUTHORIZE, authorize_params(self.app, challenge))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['Content-Security-Policy'], "frame-ancestors 'none'")
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Pragma'], 'no-cache')
        mark.assert_not_called()
        self.assertFalse(hasattr(response.wsgi_request, 'survey_frame_ancestors'))

    def test_token_and_registration_responses_are_uncacheable(self):
        """
        GIVEN /oauth/token/ and /oauth/register/
        WHEN they answer, success or error
        THEN no-store and Pragma: no-cache
        """
        bad = self.client.post(TOKEN, {'grant_type': 'authorization_code', 'code': 'nope',
                                       'client_id': self.app.client_id})
        self.assertEqual(bad['Cache-Control'], 'no-store')
        self.assertEqual(bad['Pragma'], 'no-cache')
        reg = self.client.post('/oauth/register/', 'not json', content_type='application/json')
        self.assertEqual(reg['Cache-Control'], 'no-store')
        self.assertEqual(reg['X-Frame-Options'], 'DENY')

    def test_error_page_has_the_headers_too(self):
        """
        GIVEN an unknown client
        WHEN the error page renders
        THEN DENY and no-store
        """
        response = self.client.get(AUTHORIZE, {'client_id': 'nobody', 'response_type': 'code'})
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['Cache-Control'], 'no-store')


@OAUTH
class ScrubTest(TestCase):
    def test_oauth_paths_keep_only_path_and_method(self):
        """
        GIVEN an error captured on /oauth/token/ with a code in the tags
        WHEN the scrubber runs
        THEN only path and method remain
        """
        from mapsurvey.settings import _posthog_scrub_tags
        out = _posthog_scrub_tags({'$request_path': '/oauth/token/', '$request_method': 'POST',
                                   'code': 'abc', 'Authorization': 'Bearer msa_x', '$ip': '1.2.3.4'})
        self.assertEqual(set(out), {'$request_path', '$request_method'})
