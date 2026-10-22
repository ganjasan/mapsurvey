## Why

Nothing in the product authenticates anything but a browser session. The REST API (#380), the MCP server (#306) and the OAuth 2.1 server (#313) each need the same four things — a token a client presents, a server-side check that turns it into a user with rights, a page where the creator sees and revokes what they connected, and a Pro gate — and if each builds its own we get three token tables, three `authenticate()`s and three places to forget `is_active`. This change builds that layer once (epic #378, item 1, issue #379); every later item is a resource server on top of it.

## What Changes

- New Django app `api/` holding the authorization layer: `django-oauth-toolkit` installed with its RFC 9700 compliance settings (hashed tokens at rest, PKCE S256 only, refresh rotation with reuse detection, no implicit/password/client-credentials grants). Only the models and the validation path are used here; the OAuth endpoints are #313.
- **Personal access tokens**: rows of the same access-token table with no client application, a scope set, an audience set (REST API, MCP server, or both), an optional workspace binding and a long or creator-chosen expiry. Prefix `msk_`, shown once.
- **One `authenticate(request, audience)`** — bearer header only, no session-cookie fallback, hashed constant-time lookup, expiry, revocation, audience, and `user.is_active` on every call. Returns a `Principal`.
- **Scopes registry** (`surveys:read`, `surveys:write`, `surveys:publish`, `surveys:delete`, `responses:read`) and rights helpers that intersect scope with organisation role and survey collaborator role through the existing `get_effective_survey_role`; lookups that answer 404 for anything the user cannot see and that always filter integer ids by their survey.
- **Pro gate**: feature `api` in `billing/features.py`; `require_pro_api(principal, organization)` checked at the resource per request on the organisation that owns the object, answering `403 pro_required` with an upgrade link; a lapsed subscription stops access without touching tokens.
- **Rate limits** per token (not per IP): per-minute windows for reads and writes, a daily call cap, a registry of named daily caps for expensive actions (survey create/delete, import) that resource servers hit by name, plus a per-IP limit on failed bearer attempts so a token cannot be brute-forced behind Cloudflare's shared addresses. `429` with `Retry-After`.
- **Connections page** `/editor/account/connections/` (tokens now; connected apps after #313) replacing the body of the agent-access teaser; `/editor/account/mcp/` and its URL name survive as a redirect, the account-menu and help-menu entries lose the *soon* badge and point at the new page; the "Tell me when it's ready" interest button stays until the MCP server ships.
- `GET /api/v1/me` — the one resource endpoint of this change: who the token is, which workspaces it reaches and on which plan, which scopes and audiences it holds. It is what makes a freshly minted token testable with `curl` and what every client calls first to learn `pro_required` before it happens.
- **Audit and log hygiene**: `AuditLog` actions for token created/revoked; `Authorization` scrubbed from PostHog error capture; no token value ever stored or logged.
- `manage.py check --deploy` asserts the OAuth settings stay compliant, run from a test.

No breaking changes: no existing route, model or template behaviour is removed; `/editor/account/mcp/` keeps working.

## Capabilities

### New Capabilities
- `api-authentication`: bearer-only `authenticate()`, token validation rules (hash, expiry, revocation, audience, account state), the `Principal`, the error envelope for 401.
- `personal-access-tokens`: creating, listing and revoking personal tokens on the connections page; value format, one-time display, scopes, audiences, workspace binding, expiry, `last_used_at`; audit rows.
- `api-access-rights`: the scopes registry and how a request's effective rights are the intersection of scope, organisation role and survey role; 404-not-403 lookups; the `/api/v1/me` endpoint.
- `api-pro-gate`: the `api` feature, per-request gating on the owning organisation, `403 pro_required`, behaviour across subscription states and mixed-workspace users.
- `api-rate-limits`: per-token minute windows and daily cap, the named-cap registry, the per-IP failed-attempt limit, `429` shape, fail-open behaviour.

### Modified Capabilities
- `agent-access-teaser`: the page's body and location change — `/editor/account/mcp/` redirects to `/editor/account/connections/`, which hosts the tokens UI and keeps the interest button; the *soon* badge goes.
- `audit-log`: two new audited actions (`api_token_create`, `api_token_revoke`) that have no target survey.

## Impact

- **Dependencies**: `django-oauth-toolkit` (new; `oauth2_provider` in `INSTALLED_APPS`, its migrations). `django-ratelimit` is already installed.
- **Code**: new `api/` app (`auth.py`, `scopes.py`, `rights.py`, `gates.py`, `limits.py`, `errors.py`, `models.py`, `views.py`, `urls.py`, templates, tests); `billing/features.py` (+`api`); `survey/models.py` (`AuditLog.ACTION_CHOICES`); `survey/urls.py` (teaser redirect); the two base templates' account menus and `_help_menu.html`; `mapsurvey/settings.py` (`OAUTH2_PROVIDER`, `_posthog_scrub_tags`, API constants); `mapsurvey/urls.py` (mount `api/`).
- **Database**: `oauth2_provider` tables; one new table `api_tokenprofile` (label, kind, audiences, organisation, last_used_at, revoked_at) keyed to the DOT access token.
- **Security surface**: a second credential kind reaches the application. Mitigated by bearer-only paths (no cookie ⇒ no CSRF), hashed storage, per-token and per-IP limits, `is_active` per call, audience checks, and the test checklist in #379.
- **Help centre**: `how-to/use-the-mcp-server.md` and `reference/mcp-tools.md` stay drafts; a new how-to "Personal tokens" describes the connections page.
- **Not affected**: respondent surfaces, `SurveyEvent`, billing webhooks, the editor's own views (they keep session auth; nothing here touches them).
