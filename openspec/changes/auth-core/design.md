## Context

Every request the application serves today is authenticated by a session cookie (creators) or by nothing (respondents, with a survey-session key in the cookie or, when framed, in `X-MS-Session`). Epic #378 adds a second kind of principal — a client holding a token — and three consumers of it: the OAuth 2.1 server (#313), the REST API (#380) and the MCP server (#306). This change is the layer under all three.

Constraints that shape it:
- **Pro is an organisation property** (`billing.entitlements.for_organization`), checked per call, never cached across requests, never a column. Any API gate must read it the same way.
- **Roles already exist** (`survey/permissions.py`: `ORG_ROLE_RANK`, `SURVEY_ROLE_RANK`, `get_effective_survey_role`) and `check_survey_access` answers 404, not 403, to anyone who may not see a survey. The API must not become a side door that answers differently.
- **`CROSS_SITE_COOKIES`** makes the session cookie `SameSite=None` in production (embedding). Any endpoint that accepted the cookie as credentials would be a CSRF target from any site; API paths therefore must not accept it at all.
- **Cloudflare** fronts production, so per-IP limits alone would throttle whole offices and would not stop one creator's runaway agent.
- **Workers keep the RSS of their largest request and recycle** (`layer-memory-diet`); nothing here may hold a worker (no long polls, no streams).
- **Owner decisions** (2026-10-21): one platform-wide OAuth, API and MCP behind Pro, rate limits per token as well as global caps.

## Goals / Non-Goals

**Goals:**
- One token table and one `authenticate()` that #313's OAuth tokens will satisfy without a second code path.
- Personal tokens a creator can mint, see and revoke today, testable with `curl` against `/api/v1/me`.
- Rights resolution, Pro gate, rate limits and the error envelope as importable helpers, so #380 and #306 contain no security logic of their own.
- Every rule in #379's security checklist is a test in `api/tests/`.

**Non-Goals:**
- OAuth endpoints, consent, DCR, CIMD, protected-resource metadata (#313).
- Any survey resource beyond `/me` (#380), any MCP transport (#306).
- A framework choice for the REST API (`django-ninja` is proposed in #380; `/me` here is a plain view and moves then).
- Kill switch: none (owner rule). Rollback is a revert; tokens stay in the database unused.

## Decisions

**D1. `django-oauth-toolkit` is the token store; personal tokens are `AccessToken` rows with `application=NULL`.**
Alternatives: a hand-written `ApiToken` model (simpler today, but #313 would then have two token tables or a migration), or `authlib`'s Django integration (less complete DCR/metadata support). DOT 4.x ships RFC 8414 metadata, DCR (RFC 7591/7592), PKCE enforcement, refresh rotation with reuse detection and hashed token storage; using its `AccessToken` for personal tokens means `authenticate()` is one lookup for both credential kinds. A `TokenProfile` row (OneToOne to the access token) carries what DOT has no column for: `kind` (`personal` | `oauth`), `label`, `audiences` (list of `api` | `mcp`), `organization` (optional binding), `last_used_at`, `revoked_at`, `created_by_ip`. DOT's own `Application`/`Grant`/`RefreshToken` tables are installed now and used by #313.

**D2. Settings pin RFC 9700 and hashed storage; a test runs DOT's system checks.**
`OAUTH2_PROVIDER` gets the compliance block (`COMPLIANT_BCP_RFC9700_*` all `True`, `PKCE_REQUIRED=True`, `REFRESH_TOKEN_REUSE_PROTECTION=True`, `REFRESH_TOKEN_GRACE_PERIOD_SECONDS=0`, `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE=True`, `ALLOWED_REDIRECT_URI_SCHEMES=["https"]`, `ACCESS_TOKEN_EXPIRE_SECONDS=3600`, `SCOPES` from `api/scopes.py`, `DEFAULT_SCOPES=["surveys:read"]`). Grants `implicit`, `password`, `client_credentials` are disabled through DOT's allowed grant settings. `ApiSettingsTest` runs `django.core.checks.run_checks()` restricted to DOT's checks (fallback: asserts the values) so a drift back to an insecure default fails CI rather than `check --deploy`, which this project does not run.

**D3. Token value and storage.**
Value = `msk_` + 43 URL-safe characters from `secrets.token_urlsafe(32)`. The prefix is for secret scanning and for `authenticate()` to refuse non-tokens before touching the database. Storage follows DOT's compliant mode (the `token` column holds the hash, `token_checksum` the SHA-256 used for lookup) — the exact write path (`AccessToken.objects.create(token=cleartext)` hashing on save vs. passing the hash) is confirmed against the installed version in the first task, and the creation helper lives in one place, `api/tokens.py::mint_personal_token()`. The page shows the value once and then only `msk_…` + last four characters. "Never expires" is `expires = now + 100 years` because DOT's `expires` is not nullable.

**D4. `authenticate(request, audience) -> Principal | None` is the only entry.**
Order, chosen so the cheapest refusals come first and no step leaks existence: (1) `Authorization` header present and `Bearer <value>`; otherwise `None` (never the session). (2) Per-IP failed-attempt limit consulted (D8) — exceeded ⇒ `ApiError(429)`. (3) Prefix and length sane, else record a failure, `None`. (4) SHA-256 → `AccessToken` by `token_checksum`, `select_related('user', 'profile', 'profile__organization')`. (5) Not expired, `profile.revoked_at IS NULL`, `audience in profile.audiences`. (6) `user.is_active` (django-registration leaves it `False` until activation; `confirm_phishing` sets it `False` — both end API access on the next call). (7) `last_used_at` touched if older than 60 s (`update_fields`, never a full save). Returns `Principal(user, scopes: frozenset, organization: Organization | None, token_id, kind)`. Every refusal in 3–6 is the same `401 invalid_token` with `WWW-Authenticate: Bearer realm="mapsurvey"` and counts as one failed attempt. A session cookie on an API path is ignored entirely: API views are decorated with `@api_endpoint(audience, scopes=...)`, which is `csrf_exempt`, resolves the principal from the header, stores it as `request.principal` and never reads `request.user`; `api/tests/test_auth.py` posts with a logged-in client and no header and expects 401.

**D5. Rights = scope ∩ organisation role ∩ survey role, through existing helpers.**
`api/scopes.py` is the registry (`SCOPES` ordered dict, labels for the token form and the consent page, `WRITE_SCOPES`). `api/rights.py`: `require_scope(principal, scope)` ⇒ `403 scope_missing`; `survey_for(principal, uuid, min_role='viewer')` ⇒ `get_effective_survey_role` on `principal.user`, 404 when `None` or below `min_role` (no 403: a token must not enumerate what the browser cannot); honours a profile `organization` binding (survey of another workspace ⇒ 404). `section_for(principal, survey, id)` / `question_for(principal, survey, id)` always filter by the survey (integer ids). Draft/live rules are not re-implemented: `#380`'s service layer calls `_edit_locks` etc.; this layer only answers "who, with which scopes, may see which survey".

**D6. Pro gate at the resource, per request, on the owning organisation.**
`billing/features.py` gets `'api': Feature('api', {PLAN_PRO}, _('REST API, MCP server and personal tokens'))`. `api/gates.py::require_pro_api(principal, organization)` raises `ApiError(403, 'pro_required', upgrade_url=<billing page of that organisation>)` unless `for_organization(organization).has('api')`. The organisation is the object's (`survey.organization`), never the token's: a Free collaborator on a Pro workspace's survey passes (that workspace paid), a Pro user on a Free workspace's survey does not — the same rule `unbranded` follows. `gates.pro_organizations(principal)` returns the user's organisations holding the feature plus the count that do not, for list endpoints (`hidden_by_plan`). A token is never refused or revoked for plan reasons; the personal-token form is available on Free with a note, so a trial-to-Pro path needs no re-minting. Alternative considered: gate at token issue — rejected because a lapsed subscription would then keep working until expiry and renewal would need re-minting.

**D7. Error envelope and headers.**
`api/errors.py`: `ApiError(status, code, detail='', **extra)`; the `@api_endpoint` decorator turns it into `JsonResponse({"error": code, "detail": ..., **extra}, status=...)`. Stable codes from this change: `invalid_token` (401), `scope_missing`, `pro_required` (403), `not_found` (404), `rate_limited` (429). All API responses carry `Cache-Control: no-store`. Unhandled exceptions become `500 {"error": "server_error"}` with no trace and are still captured by PostHog (D10).

**D8. Rate limits: per token, per named action, per IP for failures. All through `django-ratelimit`.**
`api/limits.py`:
- `check_request(principal, method)` — groups `api.read` (`600/m`), `api.write` (`60/m`, methods other than GET/HEAD/OPTIONS), `api.day` (`5000/d`), key `tok:<token_id>`. Called by `@api_endpoint` after authentication, before the view. Exceeded ⇒ `429 rate_limited` with `Retry-After` (seconds to the window edge; `django-ratelimit` exposes `time_left`).
- `hit(principal, action)` — the named daily caps resource servers call explicitly: `DAILY_CAPS = {'survey_create': 50, 'survey_delete': 20, 'survey_import': 20, 'export': 100}`; unknown name is a programming error (`KeyError`), so a new expensive action must be registered.
- `auth_failure(request)` / `auth_failures_exceeded(request)` — group `api.auth_fail`, `30/m` keyed by client IP (`REMOTE_ADDR` after `CloudflareIPMiddleware`). Only 401s increment, and the check runs before the database lookup, so guessing tokens costs the guesser, not us, and the equal-timing property of D4 is preserved.
- Fail-open follows `RATELIMIT_FAIL_OPEN=True` (as registration does); a Redis outage is logged once per process, not per request.
Limits are constants in the module with a `settings.API_RATE_LIMITS` override for previews and tests. Why not per IP for the main budget: Cloudflare and offices share IPs; why not per user: a creator may run two integrations and one runaway agent should not take the other down.

**D9. Connections page lives in the `api` app and replaces the teaser's body; the teaser URL redirects.**
`/editor/account/connections/` (`editor_account_connections`, `login_required`, extends `editor/editor_base.html`): tokens table (label, `msk_…abcd`, scopes, audiences, workspace or "all", created, expires, last used, *Revoke* POST), create form (label; scopes as checkboxes with `surveys:publish` and `surveys:delete` unchecked; audiences both checked; workspace select of the user's memberships or "all"; expiry 90 days / 1 year / never), one-time value banner after creation (value held in the session for exactly one render, then deleted). "Connected apps" section is a placeholder sentence until #313. The MCP interest block (example prompt, "Tell me when it's ready" POST writing `agent_access_requested_at`) moves here unchanged so `agent-access-teaser`'s event keeps flowing. `/editor/account/mcp/` becomes a 302 to the new page and keeps its URL name; the account menus and the "?" menu point at the new page and drop the *soon* badge. The spec delta records this.

**D10. Audit, analytics and log hygiene.**
`AuditLog.ACTION_CHOICES` += `api_token_create`, `api_token_revoke` (`survey=None`, metadata `token_id`, `label`, `scopes`, `audiences`, `expires`). PostHog creator events `api_token_created`, `api_token_revoked` (properties: scopes, audiences, expiry choice — no label, it is free text) and `api_token_first_use` (once, when `last_used_at` goes from null). `_posthog_scrub_tags` gains a rule that drops any tag whose name is `$request_headers`/`Authorization`-like and, for paths under `/api/` or `/mcp/`, keeps only path and status; a test raises inside an API view with a bearer and asserts the captured event contains no substring of the token. No log line anywhere formats `request.META['HTTP_AUTHORIZATION']`.

**D11. `/api/v1/me` is a plain Django view.**
`GET /api/v1/me` → `{user: {id, username, email}, workspaces: [{id, slug, name, role, plan, api: bool}], token: {kind, scopes, audiences, organization, expires, label}}` behind `@api_endpoint('api', scopes=())` — no scope needed, no Pro needed, because its purpose is to explain `pro_required` before it happens. Written without a framework so this change does not pre-empt #380's choice; #380 re-homes it.

## Risks / Trade-offs

- [DOT 4.x API differs from the docs read (compliant-mode write path, check tags)] → the first task is a spike in the shell against the installed version; `mint_personal_token()` isolates the dependency to one function.
- [Hashed storage means a lost value is unrecoverable] → that is the point; the page says so beside the one-time banner, and minting a second token costs nothing.
- [Redis outage ⇒ limits fail open] → consistent with registration; `api.day` would be the only hard stop lost, and the Pro gate and roles still hold. Logged once per process.
- [`oauth2_provider` installs admin pages for Applications and tokens that show token hashes] → read-only admin registration; staff see labels and hashes, never values (the value exists only in the one-time response).
- [A Free collaborator on a Pro survey gets API access the Free workspace never paid for] → intended: the Pro workspace owns the data; matches `unbranded`.
- [`/me` on a plain view and later on `django-ninja`] → contract documented in the spec; the move is a refactor with the same tests.
- [Per-IP failure limit throttles a NAT'd office that fat-fingered a token] → 30/min is generous for humans; the 429 says why and resets in a minute.
- [Migrations for `oauth2_provider` run in Render's pre-deploy] → all additive; no `RemoveField`, so the old instance keeps serving during the window.

## Migration Plan

1. Pipfile + settings + `INSTALLED_APPS` (`oauth2_provider`, `api`); `migrate` (DOT tables + `api_tokenprofile` + `AuditLog` choices — all additive).
2. Deploy; nothing is user-visible until the connections page link ships in the same deploy (menus switch from the teaser to the page). Tokens on Free workspaces mint fine and answer `pro_required` on `/me`'s workspace list — that is the upgrade prompt.
3. Rollback: revert the PR. Tables remain, unused; nothing else depends on them.

## Open Questions

- DOT's RFC 8707 `resource` handling for OAuth tokens is #313's concern; this change keeps audience on `TokenProfile` and #313 fills it from `resource`. Confirm in #313 that DOT exposes the parameter to the validator.
- Expiry choices: 90 days / 1 year / never — "never" is the GitHub default and what agents' config files assume; revisit if the security review of #313 wants a ceiling.
- Whether `api_token_first_use` should also email the creator ("a token was used for the first time") — out of scope here, noted for #313's connected-apps mail.
