## Context

`auth-core` (#379) left the platform with: django-oauth-toolkit (DOT) 3.4.1 holding every token we
issue, the `OAUTH2_PROVIDER` block pinned to RFC 9700 (hashed storage, PKCE S256, refresh rotation
with reuse protection, `https`-only redirects, no implicit/password), `api.auth.authenticate()` as
the one reader, `TokenProfile` beside every access token, the scopes registry, the Pro gate and the
limits. No OAuth URL is mounted yet; `TokenProfile.kind = "oauth"` exists but nothing writes it.

The issue was drafted assuming DCR, CIMD and the metadata document would be custom code. DOT 3.4.1
ships all three (`views/dynamic_client_registration.py`, `cimd.py` with an SSRF-hardened fetcher,
`views/metadata.py` for RFC 8414 and RFC 9728), plus RFC 8707 `resource` on grants and tokens,
RFC 9207 `iss`, grant narrowing at the token endpoint and `invalid_target` for malformed
indicators. The design therefore mounts and configures the toolkit and writes our own code only
where the toolkit has no opinion: loopback redirects, the audience mapping, the token profile, the
consent page and its memory, DCR abuse controls, the connected-apps page, and the response headers.

Constraints that shape it:

- `OAUTH2_PROVIDER_APPLICATION_MODEL` is pinned to `oauth2_provider.Application` and the tables
  exist in production — swapping the model now is the Django limitation DOT warns about. Every
  customisation goes through the validator class, view subclasses, a fetcher subclass, settings and
  signals, never a swapped model.
- `SurveyEmbedMiddleware` drops `X-Frame-Options` only on responses `check_survey_access` marked;
  the consent page must be unframeable regardless.
- Pro is checked at the resource per request (`api.gates`), never at consent.
- The public repo rule: no customer names in the change; test callbacks use the documented
  `claude.ai` / `chatgpt.com` URLs, which are product facts.

## Goals / Non-Goals

**Goals:**
- claude.ai custom connector, ChatGPT connector (Developer mode) and Claude Code
  (`claude mcp add --transport http`) complete sign-in → Allow → token with no manual token copy.
- Every token the server issues is a row `authenticate()` understands, with the audience the client
  asked for, so #380 and #306 need nothing from this change.
- The security checklist in #313 is a test module, not a wiki page.
- A PR preview is a complete, isolated authorization server for its own host.

**Non-Goals:**
- Protected-resource metadata (RFC 9728) and `WWW-Authenticate: … resource_metadata=` — those
  belong to each resource server (#380, #306); the AS metadata is mounted alone.
- OIDC id tokens, `client_credentials`, device flow, introspection, enterprise SSO, directory
  listings (ChatGPT apps, Claude connectors).
- A creator-facing UI to register applications; first-party clients are rows in the admin.
- Per-workspace consent (choosing which workspaces a grant reaches). The grant reaches every
  workspace the user is a member of, like a personal token without a binding; the page says so.

## Decisions

### D1. Mount DOT's views under `/oauth/` with our own URL list, metadata at the root

`api/urls.py` builds the `oauth2_provider` namespace by hand instead of including
`oauth2_provider.urls`: `authorize/`, `token/`, `revoke/` (RFC 7009; DOT's default name is
`revoke_token/`, the metadata view reverses by URL *name* `revoke-token`, so the path is ours),
`register/` and `register/<client_id>/` (DCR + RFC 7592). The namespace name must stay
`oauth2_provider` because the metadata view, the admin and DOT's own templates `reverse()` it. The
RFC 8414 document is `path('.well-known/oauth-authorization-server', OAuthServerMetadataView)` at
the root — RFC 8414 clients look there and nowhere else. Not mounted: device, introspect,
`applications/`, `authorized_tokens/`, every OIDC route, the issuer-path and PRM forms.
*Alternative*: `include('oauth2_provider.urls')` under `/oauth/` — publishes ten routes we do not
want, including a second metadata document at `/oauth/.well-known/…` and a PRM document claiming
`mapsurvey.org` is a resource.

### D2. Issuer is the deployment's own origin

`OIDC_ISS_ENDPOINT` (DOT uses it for RFC 8414 `issuer`, every endpoint URL in the document and the
RFC 9207 `iss` parameter despite the name) is `settings.OAUTH_ISSUER` = `https://<RENDER_EXTERNAL_HOSTNAME>`
when `IS_PULL_REQUEST` is `true`, else `SITE_URL`. `render.yaml` sets `SITE_URL=https://mapsurvey.org`
on previews too (mail links must point at production), so deriving the issuer from `SITE_URL` alone
would make a preview's metadata send clients to production's token endpoint. Tests run with
`OAUTH_ISSUER='https://testserver'`.

### D3. Loopback redirects: widen the scheme list, enforce the host rule in one helper

DOT validates redirect schemes in `Application.clean()` against `ALLOWED_REDIRECT_URI_SCHEMES`
(DCR and CIMD both call `full_clean()`), and matches at authorize time with exact string
comparison. Neither has a loopback exception, and `COMPLIANT_BCP_RFC9700_REDIRECT_URI_SCHEME=True`
turns `http` in the list into check error `oauth2_provider.E003`. The model cannot be subclassed
(see Context), so:

- `ALLOWED_REDIRECT_URI_SCHEMES = ['https', 'http']` and `SILENCED_SYSTEM_CHECKS += ['oauth2_provider.E003']`,
  with the reason in a comment: `http` is accepted for loopback hosts only, by the helper below.
- `api/oauth/redirects.py`: `is_loopback(uri)` (scheme `http`, host `127.0.0.1`, `[::1]` or
  `localhost`, no userinfo, no fragment), `check_registrable(uris)` (every `http` URI must be
  loopback, raises `ValidationError`), `matches(requested, registered)` (loopback: scheme + host +
  path + query equal, port ignored; otherwise exact string). Called from: the DCR view subclass and
  the CIMD fetcher subclass before DOT's `full_clean()`, a `pre_save` receiver on `Application` as
  the backstop for the admin and the shell, and the validator's `validate_redirect_uri` at
  authorize and token time.
- `test_settings` asserts the new list, the silenced id, and that a non-loopback `http` redirect is
  refused on every path — the check that used to be the toolkit's is now ours.
*Alternative*: keep `['https']` and register loopback clients with a dummy `https` redirect, matching
loopback at authorize only — breaks DCR for Claude Code, which registers its real loopback URI.

### D4. One validator subclass: `api.oauth.validator.MapsurveyOAuth2Validator`

`OAUTH2_VALIDATOR_CLASS` points at it. It overrides:
- `validate_redirect_uri` → `redirects.matches` against `request.client.redirect_uris`.
- `_create_access_token` → `super()`, then `TokenProfile.objects.create(token=…, kind="oauth",
  label=application.name[:80], suffix=value[-4:], audiences=audiences.for_resources(access_token.resource),
  code_checksum=sha256(code) when issued from a code)`. The checksum of the authorization code
  comes from `request.code` (oauthlib keeps it on the request during the `authorization_code`
  grant); on a refresh it is copied from the source token's profile so the whole family stays
  traceable to its code.
- `validate_code` → `super()`; when it returns `False` because the grant is gone, look up
  `TokenProfile.objects.filter(code_checksum=sha256(code), token__application=client)` and revoke
  each (`tokens.revoke(profile)` + `RefreshToken.revoke_family` on the family of its refresh token).
  RFC 6749 §4.1.2 wants this; DOT only answers `invalid_grant`. The lookup costs one indexed
  query on the failure path only.
- `_check_and_set_request_resource` → `super()` (shape + narrowing against the grant), then
  `audiences.for_resources()` so an unknown resource is `invalid_target` at the token endpoint too.
Token value prefixes: `ACCESS_TOKEN_GENERATOR = 'api.oauth.tokens.generate_access_token'` (`msa_`
+ `token_urlsafe(32)`), `REFRESH_TOKEN_GENERATOR` (`msr_`). `api.tokens.looks_like_token` accepts
`msk_` and `msa_`; `msr_` never reaches `authenticate()`. The prefix is what keeps the cheap
pre-check in `authenticate()` and the log scrubber honest.

### D5. Audience from `resource`

`settings.API_RESOURCE_URLS = {'api': OAUTH_ISSUER + '/api/', 'mcp': MCP_RESOURCE_URL}` where
`MCP_RESOURCE_URL` defaults to `OAUTH_ISSUER + '/mcp/'` until #306 names the host.
`api/oauth/audiences.py::for_resources(resources)`: empty list → `['api', 'mcp']` (a client that
sends no indicator — a QGIS plug-in — gets both, like a personal token with both boxes); each
indicator must be a URL-prefix match (DOT's `validate_resource_as_url_prefix`, the same rule the
resource servers will apply) of exactly one entry, the result is the set of matched keys; anything
else raises `invalid_target`. Checked in `AuthorizationView.get()` after DOT validated the request
(so the error can safely redirect to the registered URI with `state`) and in the validator at the
token endpoint. The audience lands in `TokenProfile.audiences`, which is what `authenticate()`
already checks — the token's `resource` column stays the raw list for the audit trail.

### D6. Consent page: our view, our form, our memory

`api.oauth.views.AuthorizationView(oauth2_provider.views.AuthorizationView)`:
- `template_name = 'api/authorize.html'` extending `editor/editor_base.html` (the connections page's
  base); context adds `redirect_host` (from `redirect_uri`), `client_host` (the CIMD `client_id` host
  when the id is a URL, else the redirect host), `workspaces` (memberships with plan and `api`
  entitlement), `any_pro`, the requested scopes split into `granted` (read/write/responses) and
  `switches` (`DANGEROUS_SCOPES`, rendered as checkboxes, unchecked). The client name is shown
  after the host and truncated to 60 characters; `logo_uri` is never read.
- `form_class = ConsentForm(AllowForm)`: `clean()` recomputes `scope` as the requested
  non-dangerous scopes plus the switches the user ticked; a scope the client did not request can
  not be added (hidden-field tampering), so the issued scope ⊆ requested, which OAuth permits — the
  token response carries `scope`.
- `get()` first: `state` longer than 512 bytes → error page `invalid_request` (no redirect: the
  point of the cap is not to echo it); then DOT's validation; then D5's audience check; then
  **memory**: `REQUEST_APPROVAL_PROMPT` stays `force` and we skip the page ourselves when the user
  holds an unrevoked `RefreshToken` for this application whose access token `allow_scopes(requested)`
  (DOT's `auto` looks at live access tokens only, which last an hour). A client asking for a scope the
  user did not grant last time re-prompts. First-party applications use DOT's `skip_authorization`.
- `Cancel` is DOT's `allow=False` path: redirect to the registered URI with `error=access_denied`
  and the untouched `state`. An unregistered or malformed `redirect_uri` is oauthlib's fatal error:
  DOT renders the template with `error` and no `Location` — the template's error branch is ours too.
- The login redirect is `LoginRequiredMixin`'s `?next=`; Django's login view already refuses an
  off-host `next`. `prompt=login` is DOT's.

### D7. Headers on `/oauth/*` in one middleware

`api.middleware.OAuthResponseHeadersMiddleware`, right after `SecurityMiddleware`: for a request path
under `/oauth/`, set `Cache-Control: no-store`, `Pragma: no-cache`, `X-Frame-Options: DENY` and
`Content-Security-Policy: frame-ancestors 'none'` (only when no CSP is present, the same courtesy
`SurveyEmbedMiddleware` extends). One place, every view — DOT's, ours, and the ones #306 may add
under the prefix. `SurveyEmbedMiddleware` acts only on `request.survey_frame_ancestors`, which only
`check_survey_access` sets; a test asserts the consent page response carries `DENY` with that
middleware in the stack and that `mark_embeddable` was never called on the request. The metadata
document at `/.well-known/` is not under the prefix and stays cacheable (it changes with deploys only).

### D8. DCR: open, rate-limited, normalised; CIMD: the toolkit's fetcher plus our rules

- `DCR_ENABLED = True`, `DCR_REGISTRATION_PERMISSION_CLASSES = ('oauth2_provider.dcr.AllowAllDCRPermission',)`
  — neither ChatGPT nor claude.ai can authenticate to register. `DCR_REGISTRATION_TOKEN_EXPIRE_SECONDS`
  left at the default (the RFC 7592 token lives with the registration). The registration token is
  an `AccessToken` with scope `oauth2_provider:registration` and no profile: `authenticate()`
  refuses it (no prefix, no profile) — a test says so.
- `api.oauth.views.RegistrationView(DynamicClientRegistrationView)`: `post()` runs the limiter
  first — `django_ratelimit.core.is_ratelimited` with groups `oauth.dcr.hour` (10/h) and
  `oauth.dcr.day` (50/d) keyed on `survey.abuse.client_ip`, `429` + `Retry-After` + the API error
  envelope (`rate_limited`), fail-open like the rest of `api.limits` — then normalises the body:
  `client_name` stripped of control characters, whitespace collapsed, cut to 80; `logo_uri`,
  `client_uri`, `policy_uri`, `tos_uri` dropped (never fetched, never rendered); `redirect_uris`
  through `redirects.check_registrable` (a violation is `400 invalid_redirect_uri`); then hands the
  re-serialised body (`request._body`) to DOT. `ManagementView(DynamicClientRegistrationManagementView)`
  applies the same normalisation on `PUT`.
- CIMD: `CIMD_ENABLED = True`, `CIMD_METADATA_FETCHER = 'api.oauth.cimd.MetadataFetcher'`, a
  subclass of `SafeMetadataFetcher` whose `fetch()` returns the document with the same
  normalisation and the redirect rule applied (a violation raises `CIMDError`, which the toolkit
  turns into `invalid_client`). DOT already enforces `https`, public IP after DNS resolution
  (including NAT64 and the metadata address), no redirects at all, 5 s, 16 KB, `client_id` equal to
  the URL, 5 min–24 h cache, per-URL failure backoff and an in-flight cap. The issue's "max 2
  redirects" is superseded by the toolkit's "none" — stricter, and claude.ai's and ChatGPT's documents
  are served directly.
- `purge_oauth_clients` (management command, in `reclaim.sh` after `purge_api_tokens`): delete
  `Application` rows with `registration_source` DCR or CIMD, `created` older than 30 days, no `Grant`,
  no `RefreshToken`, and no `AccessToken` other than the registration token. First-party rows
  (`registration_source = manual`) are never touched.

### D9. Connected apps

The connections page gains a *Connected apps* section above the MCP block, replacing the "Coming
soon" line: one row per `Application` for which the user holds an unrevoked `RefreshToken` or a
live access token — name, host (D6's `client_host`), scopes of the newest live access token,
created (oldest token), last used (max `TokenProfile.last_used_at` over the app's tokens),
*Disconnect*. `api.oauth.grants.disconnect(user, application)` revokes every refresh token of the
user for that application (`RefreshToken.revoke()`, which revokes its access token the toolkit way)
and marks the remaining access-token profiles `revoked_at`; writes `AuditLog(action="oauth_disconnect",
client_id, application_id)` and emits `oauth_app_disconnected` (application id, scopes, no name).
Consent writes `AuditLog(action="oauth_consent", client_id, scopes)` and emits `oauth_app_connected`
(application id, scopes, whether memory skipped the page). Another user's application id → 404.

### D10. Tests: one module per capability, the checklist as names

`api/tests/test_oauth_server.py` (metadata, authorize, PKCE, codes, tokens, refresh, resource,
revoke, headers), `test_oauth_clients.py` (DCR, CIMD with a mocked fetcher and a real resolver on
the loopback cases, redirects, purge), `test_connected_apps.py`, plus the delta cases in
`test_auth.py` (`msa_` prefix, registration token refused) and `test_settings.py`. Each checklist
line of #313 is a test method name. The flow tests drive the real endpoints with `self.client`
(session login → authorize → code → token) — no mocking of oauthlib.

## Risks / Trade-offs

- [`http` in `ALLOWED_REDIRECT_URI_SCHEMES` with E003 silenced] → the toolkit no longer guards the
  scheme; `redirects.check_registrable` is reached from four places and `test_settings` fails if a
  non-loopback `http` URI is ever accepted on any of them.
- [`request._body` rewrite in the DCR view] → a private attribute of `HttpRequest`; if a Django
  upgrade changes caching, the normalisation silently stops. Test registers a 10 000-character name
  and asserts the stored one is 80 — a regression is a red test, not a silent gap.
- [Memory skips consent while a refresh token lives (90 days)] → a stolen refresh token already
  grants everything; the page adds nothing. Disconnect ends the memory.
- [Open DCR] → rows from scanners; bounded by the limiter and purged after 30 days; `AbuseEvent`
  rows are not written for registrations (ids only in the toolkit's table) to keep the audit table
  for humans.
- [Cloudflare challenge on `/oauth/token/`] → ChatGPT's and Anthropic's egress get an HTML
  challenge and the connector shows "could not connect". The rule is an ops task; the reachability
  script (`scripts/oauth_reachability_check.py`) fetches the three endpoints and fails on a non-JSON
  body or > 10 s, run after the first deploy and after any Cloudflare change.
- [DOT behaviour on refresh: the previous access token is revoked (deleted) on rotation] → the
  `TokenProfile` goes with it (CASCADE); `last_used_at` for the connected-apps row is therefore the
  newest live token's. Acceptable: the row says "last used" and that is the current token.
- [Free workspace] → consent succeeds (the page says calls will answer `pro_required`); nothing
  else to do — the gate is at the resource.

## Migration Plan

1. Merge: `api` migration adds `TokenProfile.code_checksum` (nullable; no backfill). No change for
   personal tokens.
2. Deploy: the endpoints are live at once; nothing points to them until a client registers. The
   metadata document is the only new public page.
3. Ops, same day: Cloudflare rule for `/.well-known/*` and `/oauth/*` (skip Bot Fight Mode and
   challenges); run the reachability script against production; manual check with claude.ai,
   ChatGPT (Developer mode) and Claude Code against a preview first, then production, and record
   ChatGPT's write-tool behaviour in #306.
4. Rollback: revert the PR. Tokens already issued stop validating when their profiles' kind is
   unknown to the reverted `authenticate()`? No — `kind` is a plain string and the prefix check is
   the only gate; a revert that drops `msa_` from `looks_like_token` ends every OAuth token on the
   next call, which is the intended blast radius. DCR rows and grants stay in the toolkit's tables,
   inert, until `purge_oauth_clients` (also reverted) — delete them from the admin if needed.

## Open Questions

- MCP resource identifier: `MCP_RESOURCE_URL` defaults to `<issuer>/mcp/`; #306 decides host vs
  path and changes one setting.
- Whether to add `surveys:publish`/`surveys:delete` to the consent switches **on** when a
  first-party application asks — not needed for #306's "always confirm publish/delete" rule; left off.
