# `api/` — the authorization layer

Change `auth-core` (#379), item 1 of epic #378. Everything a programmatic client needs to be
trusted lives here; the REST API (#380), the MCP server (#306) and the OAuth 2.1 endpoints (#313)
are built on it and carry no security logic of their own.

Installed: `django-oauth-toolkit` 3.4.1 (spiked 2026-10-21).

## What is where

| Module | Holds |
|---|---|
| `models.py` | `TokenProfile`, one row beside every `oauth2_provider.AccessToken` we issue: `kind` (`personal` / `oauth`), `label`, `suffix`, `audiences`, optional `organization` binding, `revoked_at`, `last_used_at`. |
| `tokens.py` | `mint_personal_token()`, `revoke()`, `purge_ended()`, `expires_for()`. The only writer of the token table. |
| `scopes.py` | The registry (`surveys:read|write|publish|delete`, `responses:read`). Forms, `OAUTH2_PROVIDER["SCOPES"]` and every check read it. |
| `auth.py` | `authenticate(request, audience) -> Principal | None`. Bearer only. |
| `rights.py` | `require_scope`, `survey_for`, `section_for`, `question_for` — scope ∩ org role ∩ survey role, 404 never 403. |
| `gates.py` | `require_pro_api(principal, organization)`, `pro_organizations(principal)`. |
| `limits.py` | `check_request`, `hit(principal, action)`, per-IP failed-attempt budget. |
| `errors.py` | `ApiError` and the envelope. |
| `decorators.py` | `@api_endpoint(audience, scopes=())`. |
| `views.py` | `/api/v1/me` and the connections page. |

## Writing a resource endpoint

```python
from api.decorators import api_endpoint
from api import gates, limits, rights, scopes

@api_endpoint('api', scopes=(scopes.SURVEYS_WRITE,))
def create_section(request, survey_uuid):
    p = request.principal                                  # Principal: user, scopes, organization, token_id, kind
    survey = rights.survey_for(p, survey_uuid, min_role='editor')   # 404 for anything the user may not see
    gates.require_pro_api(p, survey.organization)          # 403 pro_required on a Free workspace
    limits.hit(p, 'survey_create')                         # only for the expensive actions in DAILY_CAPS
    ...                                                    # call the service layer; never touch models directly
    return {'id': section.pk}                              # dicts become JSON; raise ApiError for errors
```

Rules the decorator enforces so you do not have to: no CSRF, no session cookie (a browser's
cookie never authenticates an API path), audience check, declared scopes, the per-token
windows, `Cache-Control: no-store`, the envelope for `ApiError`, `500 server_error` with no
trace for anything else (still captured by PostHog).

## Token kinds and audiences

- **Personal** (`msk_…`, minted on `/editor/account/connections/`): `application = NULL`, a
  long or chosen expiry, audiences `api` and/or `mcp`, optional workspace binding.
- **OAuth** (`msa_…`, issued by the authorization server below): `TokenProfile.kind = "oauth"`,
  `label` = the client name, audiences from the `resource` parameter, never a workspace binding.
  Refresh tokens are `msr_…` and never reach `authenticate()`.

`authenticate(request, 'api')` refuses a token whose profile lacks `api` in `audiences`; the MCP
host asks for `'mcp'`. A REST token is not an MCP token.

## The authorization server (change oauth-server, #313)

django-oauth-toolkit's views, mounted by hand in `api/urls.py` (namespace `oauth2_provider`):

| Path | What |
|---|---|
| `/.well-known/oauth-authorization-server` | RFC 8414 document. `issuer` = `settings.OAUTH_ISSUER` (the preview's own host under `IS_PULL_REQUEST`, else `SITE_URL`). |
| `/oauth/authorize/` | Login + consent (`api/oauth/views.py`, template `api/authorize.html`). |
| `/oauth/token/` | `authorization_code` + `refresh_token` only (`api/oauth/server.py` drops the rest). PKCE S256 mandatory. |
| `/oauth/revoke/` | RFC 7009. |
| `/oauth/register/`, `/oauth/register/<client_id>/` | RFC 7591 DCR + RFC 7592, behind a per-IP budget (10/h, 50/d) and body normalisation. |

Not mounted on purpose: introspection, device flow, the toolkit's application pages, OIDC, and the
protected-resource document — that one belongs to each resource server (#380, #306).

**Clients**, three ways: open DCR (ChatGPT, claude.ai, Claude Code register themselves), CIMD (an
`https` URL as `client_id`, fetched by the toolkit's SSRF-hardened fetcher, our rules applied in
`api/oauth/cimd.py`), first-party rows in the admin (`skip_authorization` for our own tools).
`purge_oauth_clients` (nightly, `reclaim.sh`) deletes DCR/CIMD rows older than 30 days that were never
authorised.

**Redirect URIs** — `api/oauth/redirects.py` is the ONE rule: exact string match, `https` only,
except loopback `http://127.0.0.1`, `http://[::1]`, `http://localhost` with any port (RFC 8252,
Claude Code). It runs at DCR, on a CIMD document, on every `Application` save (`pre_save`) and in
the validator at authorize and token time. That is why `ALLOWED_REDIRECT_URI_SCHEMES` lists `http`
and `oauth2_provider.E003` is silenced — the toolkit cannot tell loopback from the rest.

**`resource` → audience** (`api/oauth/audiences.py`): `settings.API_RESOURCE_URLS = {'api': …,
'mcp': …}`; no indicator = both audiences; an indicator matching neither prefix = `invalid_target`.
The audience lands in `TokenProfile.audiences`, which `authenticate()` already checks.

**Consent** (`api/oauth/views.py`, `forms.py`): the redirect host is shown above the client name
(the name is attacker-chosen), `surveys:publish` / `surveys:delete` are switches off by default and
the issued scope is ⊆ the requested one (the requested set rides a signed hidden field), workspaces
and plans are listed with a Pro note when none holds `api`. A grant is remembered while an unrevoked
refresh token with covering scopes exists; more scopes re-prompt; `Cancel` → `access_denied` + `state`;
an unknown client or unregistered redirect → an error page, never a redirect; `state` > 512 bytes →
error page. A code redeemed twice revokes everything it produced (`TokenProfile.code_checksum`).
Audit `oauth_consent` / `oauth_disconnect`; events `oauth_app_connected` / `oauth_app_disconnected`.

**Headers**: `api.middleware.OAuthResponseHeadersMiddleware` puts `Cache-Control: no-store`,
`Pragma: no-cache`, `X-Frame-Options: DENY`, `frame-ancestors 'none'` on every `/oauth/*` response.

**Connected apps**: `api/oauth/grants.py` — one row per application on the connections page,
*Disconnect* revokes the refresh tokens (the toolkit revokes their access tokens) and flags the rest.

**Operations**: Cloudflare must skip Bot Fight Mode and challenges for `/.well-known/*` and
`/oauth/*` — Anthropic's egress is `160.79.104.0/21`, OpenAI publishes its ranges at
`https://openai.com/chatgpt-actions.json` / `https://openai.com/chatgpt-user.json`; a challenge page
on the token endpoint shows up in the connector as "could not connect" with no detail. After a deploy
or a Cloudflare change run `python scripts/oauth_reachability_check.py https://mapsurvey.org`
(discovery, register, token: JSON within 10 s or it fails). Manual check after the first deploy:
claude.ai custom connector, ChatGPT connector (Developer mode), `claude mcp add --transport http`;
write ChatGPT's write-tool behaviour down in #306.

## Pro

Feature `api` in `billing/features.py`. Checked **at the resource, per request, on the
organisation that owns the object** — never on the token's user and never at minting. A Free
collaborator on a Pro workspace's survey passes; a Pro user on a Free workspace's survey gets
`403 pro_required` with that workspace's `upgrade_url`. A lapsed subscription stops access on the
next call; renewal brings the same token back. `/api/v1/me` lists each workspace with `"api":
true|false` so a client can explain the refusal before it happens.

## Limits

| Group | Limit | Key |
|---|---|---|
| `api.read` | 600 / minute | token |
| `api.write` | 60 / minute (non-GET) | token |
| `api.day` | 5 000 / day | token |
| `cap.survey_create` | 50 / day | token (`limits.hit`) |
| `cap.survey_delete` | 20 / day | token |
| `cap.survey_import` | 20 / day | token |
| `cap.export` | 100 / day | token |
| `api.auth_fail` | 30 failed bearers / minute | client IP, checked before the lookup |

`429 {"error": "rate_limited", "limit": "<group>", "retry_after": <s>}` + `Retry-After`. Override
per environment with `settings.API_RATE_LIMITS = {'api.write': (10, 60), 'cap.survey_create': (3, 86400)}`.
Cache outage ⇒ fail open, one warning per process.

## Errors

`{"error": "<code>", "detail": "<text>", ...}` — codes: `invalid_token` (401, with
`WWW-Authenticate: Bearer realm="mapsurvey"`), `scope_missing` (403, `scope`), `pro_required`
(403, `organization`, `upgrade_url`), `not_found` (404), `rate_limited` (429), `server_error`
(500).

## Log hygiene

No code path logs or stores a bearer value. `_posthog_scrub_tags` in `settings.py` drops
header-shaped tags everywhere and keeps only path and method under `API_PATH_PREFIXES`.
`AuditLog` rows (`api_token_create`, `api_token_revoke`) and PostHog events carry the token id,
scopes and audiences — never the label (free text) or the value.

## Settings

`OAUTH2_PROVIDER` pins the RFC 9700 block (hashed storage, PKCE S256 only, refresh rotation with
reuse detection, exact redirect matching, no implicit/password grants) plus the authorization
server's own block (validator and server classes, token generators, 10-minute codes, DCR and CIMD
on, `OIDC_ISS_ENDPOINT = OAUTH_ISSUER`). `api.tests.test_settings` runs the toolkit's deploy-time
system check so a drift fails the suite; the one silenced id, `oauth2_provider.E003`, is the
loopback exception explained above and has its own test.

## Tests

`./run_tests.sh api` — one module per capability: `test_auth`, `test_tokens`, `test_rights`,
`test_pro_gate`, `test_limits`, `test_me`, `test_connections`, `test_settings`, `test_oauth_server`,
`test_oauth_clients`, `test_connected_apps`. Builders in `tests/helpers.py` (`LOCMEM` swaps the
cache for a local one so counters are deterministic; `oauth_settings()`, `make_app`, `pkce`,
`consent`, `grant` drive the real endpoints).

## Operations

`purge_api_tokens` and `purge_oauth_clients` (in `reclaim.sh`, nightly) delete tokens expired or
revoked more than 30 days ago and never-authorised client registrations older than 30 days. The
admin shows `TokenProfile` read-only and `Application` with registration source and token counts.
