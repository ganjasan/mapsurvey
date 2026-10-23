## 1. Settings, mounts and headers

- [x] 1.1 `settings.py`: `OAUTH_ISSUER` (preview host under `IS_PULL_REQUEST`, else `SITE_URL`), `API_RESOURCE_URLS`, `MCP_RESOURCE_URL`; `OAUTH2_PROVIDER` additions — `OIDC_ISS_ENDPOINT = OAUTH_ISSUER`, `OAUTH2_VALIDATOR_CLASS`, `ACCESS_TOKEN_GENERATOR` / `REFRESH_TOKEN_GENERATOR`, `AUTHORIZATION_CODE_EXPIRE_SECONDS = 600`, `OAUTH2_RESPONSE_TYPES_SUPPORTED = ["code"]`, `OAUTH2_GRANT_TYPES_SUPPORTED = ["authorization_code", "refresh_token"]`, `OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED` with `"none"`, `DCR_ENABLED`, `DCR_REGISTRATION_PERMISSION_CLASSES = AllowAll`, `CIMD_ENABLED`, `CIMD_METADATA_FETCHER`, `ALLOWED_REDIRECT_URI_SCHEMES = ["https", "http"]`; `SILENCED_SYSTEM_CHECKS += ["oauth2_provider.E003"]` with the comment (design D2–D5, D8)
- [x] 1.2 `api/urls.py`: the `oauth2_provider` namespace by hand — `oauth/authorize/`, `oauth/token/`, `oauth/revoke/`, `oauth/register/`, `oauth/register/<client_id>/`, root `.well-known/oauth-authorization-server`; nothing else of the toolkit's (D1)
- [x] 1.3 `api/middleware.py::OAuthResponseHeadersMiddleware` (no-store, Pragma, XFO DENY, `frame-ancestors 'none'` when no CSP) added after `SecurityMiddleware` (D7)
- [x] 1.4 `api/tests/test_settings.py`: assert the new scheme list, the silenced id, grants/response types, issuer in tests = `https://testserver`; the drift test still red on `PKCE_REQUIRED=False`

## 2. Token plumbing

- [x] 2.1 Migration: `TokenProfile.code_checksum` (CharField 64, null, db_index)
- [x] 2.2 `api/oauth/tokens.py`: `generate_access_token` (`msa_`), `generate_refresh_token` (`msr_`); `api/tokens.py::looks_like_token` accepts `msk_` and `msa_`, refuses `msr_`
- [x] 2.3 `api/oauth/audiences.py::for_resources(resources)` — empty → both, prefix match per `API_RESOURCE_URLS`, unknown → `invalid_target` (D5)
- [x] 2.4 `api/oauth/redirects.py`: `is_loopback`, `check_registrable`, `matches`; `pre_save` receiver on `Application` in `api/apps.py` (D3)
- [x] 2.5 `api/oauth/validator.py::MapsurveyOAuth2Validator`: `validate_redirect_uri`, `_create_access_token` (+ `TokenProfile` with audiences, label, suffix, `code_checksum`), `validate_code` (double redemption → revoke the family), `_check_and_set_request_resource` (+ audience check) (D4)
- [x] 2.6 `api/tests/test_auth.py`: `msa_` accepted with `kind == "oauth"`, `msr_` refused before any query, registration token refused

## 3. Authorize and consent

- [x] 3.1 `api/oauth/forms.py::ConsentForm` — scope recomputed from requested non-dangerous scopes + ticked switches, never beyond the request (D6)
- [x] 3.2 `api/oauth/views.py::AuthorizationView` — `state` cap → error page, audience check after validation, grant memory (unrevoked refresh token with covering scopes), context: `redirect_host`, `client_host`, `client_name` (≤ 60), granted / switches, workspaces with plans, `any_pro`; audit `oauth_consent` + event `oauth_app_connected` on allow (D6, D9)
- [x] 3.3 `api/templates/api/authorize.html` on `editor/editor_base.html`: host first, name second, scopes, switches, workspaces, Pro note, Allow / Cancel, error branch (`error.error`, `error.description`) with no redirect
- [x] 3.4 Product events: `OAUTH_APP_CONNECTED`, `OAUTH_APP_DISCONNECTED` in `survey/product_events.py`; audit actions `oauth_consent`, `oauth_disconnect`
- [x] 3.5 `api/tests/test_oauth_server.py`: metadata (members, S256 only, preview issuer, unmounted routes); authorize (anonymous → login `next`, no challenge, `plain`, unregistered redirect = page without `Location`, state 513 → page, state 512 round-trip, unknown resource → `invalid_target`, inactive user); consent (host before name, switches off, scope cannot be added, Free note + first call `pro_required`, Cancel → `access_denied` + state); memory (second authorize skips, more scopes re-prompts, after disconnect re-prompts); codes (`iss`, verifier mismatch, code twice → tokens revoked, resource mismatch); token (format, `expires_in`, `scope`, audience from resource, no resource → both, refresh rotation + reuse → family revoked, `client_credentials` / `password` → `unsupported_grant_type`, deactivated user); revoke (RFC 7009 public client); headers on `/oauth/*` incl. consent with `SurveyEmbedMiddleware` in the stack; audit row and PostHog scrub

## 4. Client registration

- [x] 4.1 `api/oauth/dcr.py`: limiter (`oauth.dcr.hour` 10/h, `oauth.dcr.day` 50/d on `client_ip`, fail-open) and `normalise_metadata(data)` (name strip/collapse/cut 80, drop `logo_uri`/`client_uri`/`policy_uri`/`tos_uri`, `check_registrable` on `redirect_uris`); `RegistrationView.post` and `ManagementView.put` rewriting `request._body` (D8)
- [x] 4.2 `api/oauth/cimd.py::MetadataFetcher(SafeMetadataFetcher)` — `fetch()` → `normalise_metadata`, violations raise `CIMDError` (D8)
- [x] 4.3 `api/admin.py`: `Application` admin with `registration_source`, `created`, `skip_authorization`, token counts; `TokenProfile` admin shows `kind` and `code_checksum` read-only
- [x] 4.4 `api/management/commands/purge_oauth_clients.py` + line in `reclaim.sh` after `purge_api_tokens` (D8)
- [x] 4.5 `api/tests/test_oauth_clients.py`: redirects (loopback any port, non-loopback `http` refused at DCR / CIMD / admin save, different port on non-loopback, known callbacks); DCR (201 shape, 11th in an hour → 429, 10 000-char name → 80, `logo_uri` dropped and never fetched, registration token on the API → 401, RFC 7592 PUT normalised); CIMD (private IP, metadata address, `http`, 302, 1 MB, mismatching `client_id`, valid mocked document → consent shows the host); first-party `skip_authorization`; purge (stale deleted, live kept, manual kept)

## 5. Connected apps

- [x] 5.1 `api/oauth/grants.py`: `connected_apps(user)` rows (name, host, scopes, created, last used) and `disconnect(user, application)` with audit + event (D9)
- [x] 5.2 `api/views.py::connections`: `action=disconnect` branch (404 for a foreign/unknown application), rows in context; `api/templates/api/connections.html`: Connected apps section replacing the "Coming soon" copy, empty state with the `connected_apps` help link
- [x] 5.3 `api/tests/test_connected_apps.py`: one row for two token generations, personal tokens not listed, disconnect ends access + refresh, another user's grant → 404

## 6. Docs, help, translations

- [x] 6.1 `help/src/content/docs/how-to/connect-an-app.md` "Connect ChatGPT, Claude and other apps" written as `draft: true`; the `connected_apps` registry key and the link on the connections page DEFERRED to #306 (owner decision 2026-10-23: nothing to connect to yet)
- [x] 6.2 New creator strings (consent page, connected apps) appended to the eight `TARGET_LOCALES` catalogs by hand; `compilemessages`; `TranslationCatalogHygieneTest` green
- [x] 6.3 `api/README.md`: the authorization-server contract (endpoints, DCR/CIMD, redirect rules, audiences, token prefixes, consent memory, headers, Cloudflare rule with Anthropic's `160.79.104.0/21` and OpenAI's published egress ranges, the purge command); `CLAUDE.md` API-platform paragraph updated in one sentence
- [x] 6.4 `scripts/oauth_reachability_check.py`: fetch discovery, `POST /oauth/register/` (dry: invalid body → JSON 400) and `POST /oauth/token/` (invalid grant → JSON 400) on a given origin; fail on non-JSON body or > 10 s; usage in `api/README.md`
- [x] 6.5 Changelog entry DEFERRED to #306 (owner decision 2026-10-23): announcing "connect ChatGPT" before the MCP server exists would mislead creators

## 7. Verification

- [x] 7.1 `./run_tests.sh api -v2` and `./run_tests.sh survey.tests.SurveyEmbedMiddlewareTest survey.tests.HelpSiteLinksTest survey.tests.TranslationCatalogHygieneTest`; full `./run_tests.sh survey` once before the PR
- [x] 7.2 Deprecation gate from `CLAUDE.md` over `api` (`-W error::DeprecationWarning:api`)
- [x] 7.3 Browser run on the worktree's dev server (offset 30): DCR with `curl`, authorize in Chrome as a signed-in creator, Allow, exchange the code with PKCE, call `/api/v1/me`, see the row on the connections page, Disconnect, confirm 401 — screenshot of the consent page for the PR
- [ ] 7.4 PR: `[render preview]` ONLY if the owner asks; the manual check with claude.ai, ChatGPT (Developer mode) and Claude Code is an ops step after merge, recorded in #306 (ChatGPT write-tool behaviour) and in `api/README.md`
