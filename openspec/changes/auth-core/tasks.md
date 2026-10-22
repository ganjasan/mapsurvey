## 1. Dependency spike and settings

- [x] 1.1 Add `django-oauth-toolkit` to the Pipfile, install into the worktree venv, record the installed version in `api/README.md`
- [x] 1.2 In a shell, confirm against the installed version: how `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE` writes `AccessToken.token` / `token_checksum` on create, the exact settings keys of the RFC 9700 block, how grants are disabled, and whether DOT's system checks carry a tag — note the findings at the top of `api/tokens.py`
- [x] 1.3 `mapsurvey/settings.py`: `oauth2_provider` and `api` in `INSTALLED_APPS`; `OAUTH2_PROVIDER` block per design D2 (`SCOPES` from `api/scopes.py`, access token 3600 s, hashed storage, grace 0, PKCE required, reuse protection, https-only redirect schemes); `API_RATE_LIMITS = {}` override hook; `API_PATH_PREFIXES`
- [x] 1.4 `api/tests/test_settings.py`: DOT system checks produce no errors (fallback: assert each compliance value); flipping `PKCE_REQUIRED` under `override_settings` makes the check fail

## 2. Models and minting

- [x] 2.1 `api/models.py`: `TokenProfile` (OneToOne to `oauth2_provider.AccessToken`, `kind`, `label`, `audiences` JSON, `organization` FK nullable, `last_used_at`, `revoked_at`, `created_by_ip`); migration; read-only admin that shows labels and never the token column
- [x] 2.2 `api/scopes.py`: ordered registry with labels, `WRITE_SCOPES`, `DEFAULT_SCOPES`, `is_valid(scope)`
- [x] 2.3 `api/tokens.py::mint_personal_token(user, label, scopes, audiences, organization, expires)` — value `msk_` + `token_urlsafe(32)`, one write path, returns `(value, profile)`; `revoke(profile)`; `expires_for(choice)` (90 d / 1 y / 100 y)
- [x] 2.4 `survey/models.py`: `AuditLog.ACTION_CHOICES` += `api_token_create`, `api_token_revoke`; migration
- [x] 2.5 `api/tests/test_tokens.py`: hash-only storage, value format, uniqueness, organisation must be a membership, audit rows without the value

## 3. Authentication and the endpoint decorator

- [x] 3.1 `api/errors.py`: `ApiError`, the JSON envelope, `Cache-Control: no-store`, `WWW-Authenticate` on 401, `500 server_error` without a trace
- [x] 3.2 `api/auth.py::authenticate(request, audience)` in design D4 order; `Principal` dataclass; `last_used_at` touched at most once a minute; `api_token_first_use` event
- [x] 3.3 `api/decorators.py::api_endpoint(audience, scopes=())` — `csrf_exempt`, header-only principal on `request.principal`, scope checks, rate-limit check, envelope for `ApiError` and unhandled exceptions
- [x] 3.4 `mapsurvey/settings.py::_posthog_scrub_tags`: drop header-like tags everywhere and keep only path and status under `API_PATH_PREFIXES`
- [x] 3.5 `api/tests/test_auth.py`: every scenario of `api-authentication` — session cookie without bearer → 401, query-string token, cross-site form POST, revoked/expired/inactive/wrong-audience/oversized/no-prefix all identical 401, no DB lookup for malformed values (`assertNumQueries`), last-use throttle, first-use event once, 500 envelope, PostHog capture contains no token substring

## 4. Rights, Pro gate, limits

- [x] 4.1 `api/rights.py`: `require_scope`, `survey_for(principal, uuid, min_role)`, `section_for`, `question_for` over `get_effective_survey_role` and the organisation binding; 404 only
- [x] 4.2 `billing/features.py`: feature `api`; `api/gates.py`: `require_pro_api(principal, organization)` and `pro_organizations(principal)`; `upgrade_url` from the existing billing page URL
- [x] 4.3 `api/limits.py`: `check_request` (read/write/day groups keyed `tok:<id>`), `hit(principal, action)` with `DAILY_CAPS`, `auth_failure`/`auth_failures_exceeded` keyed by client IP, `Retry-After` from `time_left`, `settings.API_RATE_LIMITS` override, fail-open with one warning per process
- [x] 4.4 `api/tests/test_rights.py`: other workspace → 404 byte-identical to random uuid, viewer below `min_role` → 404, bound token → 404 on the other workspace, section id under the wrong survey → 404, missing scope → 403 before any object load
- [x] 4.5 `api/tests/test_pro_gate.py`: registry, Free survey → `pro_required`, Free collaborator on Pro survey allowed, lapse between two calls (frozen time), renewal with the same token, refund state, `pro_organizations` counts — builders from `billing/tests/helpers.py`
- [x] 4.6 `api/tests/test_limits.py`: 61st POST → 429 with `Retry-After`, two tokens one IP independent, reads do not consume writes, named cap 51st → 429, unknown action → `KeyError`, 31 failed bearers → 429 before lookup, valid traffic unaffected, cache exception → request proceeds with one warning (cache backend patched to raise)

## 5. `/api/v1/me`

- [x] 5.1 `api/views.py::me` behind `@api_endpoint("api")`; `api/urls.py`; mount `/api/v1/` in `mapsurvey/urls.py`
- [x] 5.2 `api/tests/test_me.py`: Free + Pro workspaces listed with `api` flags, bound token lists one, response shape fixed by an exact-dict assertion, `Cache-Control: no-store`

## 6. Connections page and the teaser

- [x] 6.1 `api/forms.py::PersonalTokenForm` (label ≤ 80, scopes from the registry with publish/delete unchecked, audiences both checked, workspace choices = memberships + "All workspaces", expiry choice)
- [x] 6.2 `api/views.py`: `connections` (GET list + POST create with the one-render value banner held in the session; POST revoke by id scoped to the user → 404 otherwise); `AuditLog` rows; `api_token_created` / `api_token_revoked` creator events (no label, no value)
- [x] 6.3 Template `api/connections.html` extending `editor/editor_base.html`: tokens table (`msk_…` + last four, scopes, audiences, workspace, created, expires, last used, *Expired* marker, Revoke), create form, Free note, "Connected apps" placeholder, the MCP block (example prompt + "Tell me when it's ready" POST) moved from `editor/account_mcp.html`; works at phone width
- [x] 6.4 `survey/urls.py` + `survey/editor_views.py`: `editor_account_mcp` becomes a redirect to `editor_account_connections`, its POST handler for the interest button moves to the connections view; delete `account_mcp.html`
- [x] 6.5 `base.html`, `editor/editor_base.html`, `editor/partials/_help_menu.html`: "API & connections" without the *soon* badge; "Connect your AI agent" → connections page; `makemessages` for the new strings, Russian in the same PR
- [x] 6.6 `api/tests/test_connections.py`: all `personal-access-tokens` page scenarios + the `agent-access-teaser` delta (redirect, interest recorded once, signed-out redirect, both menus)

## 7. Cleanup, help and docs

- [x] 7.1 `api/management/commands/purge_api_tokens.py` (expired or revoked > 30 days); add to `reclaim.sh`; test
- [x] 7.2 `help/src/content/docs/how-to/personal-tokens.md` (make, scopes, workspace binding, revoke, `curl /api/v1/me`); link from `reference/plans-and-billing.md` as a Pro feature; keep the MCP how-to a draft
- [x] 7.3 `api/README.md`: settings, token kinds, audiences, limits table, how a resource server uses `api_endpoint`/`rights`/`gates`/`limits` (the contract #380 and #306 build on)
- [x] 7.4 CLAUDE.md: a short "API platform (`api/`, change `auth-core`, #379)" paragraph with the one-`authenticate()`, bearer-only, Pro-at-resource and per-token-limit rules
- [x] 7.5 Changelog entry `survey/changelog/<date>-personal-tokens.html` (kind `new`, link to the connections page)

## 8. Verification

- [x] 8.1 `./run_tests.sh api -v2` and `./run_tests.sh billing survey` green; `LayerMemoryDietTest` and `RepoHygieneTest` untouched
- [x] 8.2 `/verify`: mint a token on the dev server, `curl -H "Authorization: Bearer msk_…" /api/v1/me` on a Free and a Pro workspace, revoke, confirm 401; cookie-only request to `/api/v1/me` is 401
- [x] 8.3 Update #379 with the checklist ticked and open the PR against `master` (no `[render preview]` unless asked)
