## Why

A creator with ChatGPT or claude.ai in the browser has nowhere to paste a personal token: both
connector dialogs offer OAuth (dynamic registration or a metadata-document client id, PKCE S256) or
nothing, and Claude Code, QGIS plug-ins and Zapier-style tools want the same sign-in-and-Allow flow.
Change `auth-core` (#379) built the token table, `authenticate()`, scopes, the Pro gate and the
limits; this change (issue #313, item 2 of epic #378) puts the authorization server on top of them,
platform-wide — the REST API (#380) and the MCP server (#306) are two resource servers consuming the
same tokens — so that every programmatic client of Mapsurvey is one sign-in away.

## What Changes

- **Authorization server endpoints** (django-oauth-toolkit 3.4.1, already installed): RFC 8414
  metadata at `/.well-known/oauth-authorization-server`, `/oauth/authorize/` (login + consent),
  `/oauth/token/` (`authorization_code` + `refresh_token` only), `/oauth/revoke/` (RFC 7009),
  `/oauth/register/` (RFC 7591 DCR with RFC 7592 management). Issuer = the deployment's own origin,
  so a PR preview never issues for production. No OIDC, no `client_credentials`, no device flow, no
  introspection endpoint.
- **Clients three ways**: open DCR (rate-limited per IP, name normalised, `logo_uri` dropped,
  registrations unused for 30 days purged nightly), CIMD (an `https` URL as `client_id`, fetched by
  the toolkit's SSRF-hardened fetcher and then held to the same redirect rules), and first-party
  applications registered in the admin (`skip_authorization` for our own tools).
- **Redirect URI rules**: exact string match, `https` only — except loopback
  `http://127.0.0.1`, `http://[::1]`, `http://localhost` with any port (RFC 8252 §7.3, what Claude
  Code does). The scheme list widens to accept the loopback form; ONE helper (`api/oauth/redirects.py`)
  refuses non-loopback `http` at registration, at authorize and at token time. An unregistered or
  malformed `redirect_uri` renders an error page, never a redirect.
- **Codes and tokens**: PKCE S256 mandatory, codes single-use (10 min) bound to client, redirect,
  challenge and `resource`; a code redeemed twice revokes every token it produced. Access token 1 h
  with a `msa_` prefix, refresh token (`msr_`) rotated on every use with family revocation on reuse;
  `iss` in the authorization response; `resource` (RFC 8707) honoured on authorize and token and
  mapped to the token's audience (`api` / `mcp`) — unknown resource ⇒ `invalid_target`.
- **Consent page**: our template on the editor base, showing the redirect host above the
  client name, the requested scopes (publish/delete as switches, off by default), the workspaces the
  grant reaches and a Pro note when none of them is Pro; `Cancel` returns `access_denied` with the
  untouched `state`. A grant is remembered per client × scope set; asking for more re-prompts.
  Every `/oauth/*` response carries `X-Frame-Options: DENY`, `frame-ancestors 'none'`,
  `Cache-Control: no-store`.
- **Connected apps** on `/editor/account/connections/`: one row per authorised client with name,
  host, scopes, created, last used and *Disconnect*; the "Coming soon" copy goes.
- **`authenticate()` accepts the OAuth prefix** (`msa_`) beside `msk_`; every OAuth access token gets
  a `TokenProfile(kind="oauth")` at issuance, so rights, Pro gate and limits apply unchanged.
- **Operations**: `purge_oauth_clients` in `reclaim.sh`; a reachability script for the discovery,
  registration and token endpoints; the Cloudflare rule that keeps Bot Fight Mode off
  `/.well-known/*` and `/oauth/*`; `api/README.md` grows the contract; a help page "Connect ChatGPT,
  Claude and other apps" written now but kept `draft: true` — with the changelog entry and the help
  link, it goes live with the MCP server (#306), when there is something to connect to (owner
  decision 2026-10-23).

## Capabilities

### New Capabilities
- `oauth-authorization-server`: metadata, authorize + consent, token (codes, PKCE, refresh rotation,
  `resource` → audience), revocation, response headers on `/oauth/*`, issuer per deployment.
- `oauth-client-registration`: DCR with abuse controls, CIMD, first-party applications, the redirect
  URI rules shared by all three, purge of unused registrations.
- `connected-apps`: the grants a creator sees and disconnects on the connections page.

### Modified Capabilities
- `api-authentication`: the token validation order accepts the `msa_` prefix as well as `msk_`;
  the Principal's `kind` is `oauth` for a token minted by the authorization server; the per-IP
  failed-attempt budget is unchanged.
- `survey-embedding`: the "stay unframeable" scenario gains the OAuth consent page — `/oauth/*`
  is never marked embeddable and carries `DENY` whatever the embed middleware does elsewhere.

## Impact

- **Code**: new package `api/oauth/` (validator subclass, views, forms, redirects helper, DCR
  preprocessing, audiences, grant memory, disconnect), `api/middleware.py` (headers on `/oauth/*`),
  `api/urls.py` (mounts), `api/templates/api/authorize.html`, changes to `api/auth.py`,
  `api/tokens.py`, `api/views.py`, `api/templates/api/connections.html`, `mapsurvey/settings.py`
  (`OAUTH2_PROVIDER` block, `MIDDLEWARE`, `SILENCED_SYSTEM_CHECKS`, `API_RESOURCE_URLS`,
  `OAUTH_ISSUER`), `reclaim.sh`, `survey/help_links.py`, `help/src/content/docs/how-to/`.
- **Data**: no new table. `TokenProfile` gains `code_checksum` (nullable, indexed) for the
  double-redemption rule; one migration in `api/`. OAuth applications, grants and tokens are the
  toolkit's existing tables.
- **Dependencies**: none new — django-oauth-toolkit 3.4.1 ships DCR, CIMD, RFC 8414/8707/9207.
  `django-ratelimit` (already installed) backs the DCR limiter.
- **Settings/tests**: `test_settings` learns that `http` is in the scheme list for loopback only
  and that `oauth2_provider.E003` is silenced for that reason; new modules
  `api/tests/test_oauth_*.py` follow the one-module-per-capability rule.
- **i18n**: consent-page and connected-apps strings go into the eight maintained catalogs by hand
  (`TranslationCatalogHygieneTest.TARGET_LOCALES`).
- **Ops outside the repo**: the Cloudflare rule and a manual check with claude.ai, ChatGPT and
  Claude Code; findings about ChatGPT's write-tool behaviour are recorded in #306.
