"""Builders shared by the api test modules (one module per capability, as in billing/)."""
from django.contrib.auth.models import User
from django.test import override_settings

from billing.tests.helpers import make_org, make_sub  # noqa: F401 -- re-exported
from survey.models import Membership, Organization, Question, SurveyHeader, SurveySection

from .. import scopes, tokens
from ..models import AUDIENCE_API, AUDIENCE_MCP

ALL_SCOPES = tuple(scopes.SCOPES)

# Deterministic counters, no Redis dependency: Django swaps the cache on override.
LOCMEM = override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                                'LOCATION': 'api-tests'}})


def make_user(username='api_user', **kw):
    kw.setdefault('email', f'{username}@example.test')
    return User.objects.create_user(username=username, password='pass', **kw)


def make_member(org, username, role='owner'):
    user = make_user(username)
    Membership.objects.create(user=user, organization=org, role=role)
    return user


def make_pro_org(name='Pro Org', owner_username='pro_owner'):
    org, owner = make_org(name, owner_username)
    make_sub(org)
    return org, owner


def make_free_org(name='Free Org', owner_username='free_owner'):
    return make_org(name, owner_username)


def make_survey(org, name='api_survey'):
    survey = SurveyHeader.objects.create(organization=org, name=name)
    section = SurveySection.objects.create(survey_header=survey, name='sec1')
    question = Question.objects.create(survey_section=section, name='Q1', input_type='text')
    return survey, section, question


def mint(user, scopes_=ALL_SCOPES, audiences=(AUDIENCE_API, AUDIENCE_MCP), organization=None, expires=None,
         label='test token'):
    return tokens.mint_personal_token(user, label, scopes_, audiences, organization=organization, expires=expires)


def bearer(value):
    return {'HTTP_AUTHORIZATION': f'Bearer {value}'}


# --- the authorization server (change oauth-server) -----------------------------------
import base64  # noqa: E402
import hashlib  # noqa: E402
import html as html_lib  # noqa: E402
import re  # noqa: E402
import secrets  # noqa: E402
from urllib.parse import parse_qs, urlsplit  # noqa: E402

from django.conf import settings  # noqa: E402
from oauth2_provider.models import Application  # noqa: E402

ISSUER = 'https://testserver'
RESOURCES = {'api': ISSUER + '/api/', 'mcp': ISSUER + '/mcp/'}
AUTHORIZE = '/oauth/authorize/'
TOKEN = '/oauth/token/'
REVOKE = '/oauth/revoke/'
REGISTER = '/oauth/register/'
METADATA = '/.well-known/oauth-authorization-server'
ME = '/api/v1/me'


def oauth_settings(**extra):
    """The test client's host is `testserver`: issuer and resources follow it."""
    block = dict(settings.OAUTH2_PROVIDER, OIDC_ISS_ENDPOINT=ISSUER)
    block.update(extra)
    return override_settings(OAUTH2_PROVIDER=block, API_RESOURCE_URLS=RESOURCES, OAUTH_ISSUER=ISSUER)


def make_app(name='Test app', redirect_uris='https://app.example/cb', source='manual', skip=False, **kw):
    return Application.objects.create(
        name=name, client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=redirect_uris, registration_source=source, skip_authorization=skip, **kw,
    )


def pkce():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def authorize_params(app, challenge, scope='surveys:read', state='xyz', redirect_uri=None, **extra):
    params = {
        'response_type': 'code', 'client_id': app.client_id,
        'redirect_uri': redirect_uri or app.redirect_uris.split()[0],
        'scope': scope, 'state': state,
        'code_challenge': challenge, 'code_challenge_method': 'S256',
    }
    params.update(extra)
    return params


_HIDDEN = re.compile(r'<input[^>]*type="hidden"[^>]*>')
_ATTR = re.compile(r'(\w+)="([^"]*)"')


def form_fields(html):
    """The consent form's hidden fields, as a browser would post them."""
    fields = {}
    for tag in _HIDDEN.findall(html):
        attrs = dict(_ATTR.findall(tag))
        if 'name' in attrs:
            fields[attrs['name']] = html_lib.unescape(attrs.get('value', ''))
    return fields


def consent(client, html, allow=True, switches=()):
    from ..oauth.forms import switch_name
    data = form_fields(html)
    if allow:
        data['allow'] = '1'
    for scope in switches:
        data[switch_name(scope)] = 'on'
    return client.post(AUTHORIZE, data)


def query(location):
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query, keep_blank_values=True).items()}


def exchange(client, app, code, verifier, redirect_uri=None, **extra):
    data = {
        'grant_type': 'authorization_code', 'code': code, 'client_id': app.client_id,
        'redirect_uri': redirect_uri or app.redirect_uris.split()[0], 'code_verifier': verifier,
    }
    data.update(extra)
    return client.post(TOKEN, data)


def refresh(client, app, refresh_token, **extra):
    data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token, 'client_id': app.client_id}
    data.update(extra)
    return client.post(TOKEN, data)


def grant(client, app, scope='surveys:read', state='xyz', switches=(), resource=None, token_resource=None):
    """Signed-in `client`: authorize -> allow -> exchange. Returns the token JSON."""
    verifier, challenge = pkce()
    params = authorize_params(app, challenge, scope=scope, state=state)
    if resource:
        params['resource'] = resource
    page = client.get(AUTHORIZE, params)
    if page.status_code == 200:
        page = consent(client, page.content.decode(), switches=switches)
    assert page.status_code == 302, (page.status_code, page.content[:300])
    code = query(page['Location'])['code']
    extra = {'resource': token_resource} if token_resource else {}
    response = exchange(client, app, code, verifier, **extra)
    assert response.status_code == 200, response.content
    return response.json()
