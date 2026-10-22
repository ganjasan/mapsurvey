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
- **OAuth** (#313): issued by the authorization server; `TokenProfile.kind = "oauth"`, audience
  from the `resource` parameter.

`authenticate(request, 'api')` refuses a token whose profile lacks `api` in `audiences`; the MCP
host asks for `'mcp'`. A REST token is not an MCP token.

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
reuse detection, https-only redirects, no implicit/password grants). `api.tests.test_settings`
runs the toolkit's deploy-time system check so a drift fails the suite.

## Tests

`./run_tests.sh api` — one module per capability: `test_auth`, `test_tokens`, `test_rights`,
`test_pro_gate`, `test_limits`, `test_me`, `test_connections`, `test_settings`. Builders in
`tests/helpers.py` (`LOCMEM` swaps the cache for a local one so counters are deterministic).

## Operations

`purge_api_tokens` (in `reclaim.sh`, nightly) deletes tokens expired or revoked more than 30 days
ago. The admin shows `TokenProfile` read-only.
