# connected-apps Specification

## Purpose
The OAuth grants a creator holds, as one row per client application on `/editor/account/connections/`, and *Disconnect*, which revokes every token of that grant at once.
## Requirements
### Requirement: Connected apps are listed on the connections page
`GET /editor/account/connections/` SHALL show a *Connected apps* section listing, for the signed-in
user, one row per client application for which the user holds an unrevoked refresh token or an
unexpired, unrevoked access token: client name (≤ 60 chars shown), host (the CIMD `client_id` host,
else the first registered redirect URI's host), the scopes of the newest live access token, created
(the oldest token's time), last used (the newest `last_used_at` across the app's tokens, or "never")
and a *Disconnect* POST. The section SHALL replace the "will be listed here once that is available"
copy; with no grants it SHALL say "No connected apps yet.".

#### Scenario: One client, two token generations
- **WHEN** a user authorised a client and the client refreshed once
- **THEN** the page shows one row for that client with the newest token's scopes and the oldest token's created time

#### Scenario: Personal tokens are not apps
- **WHEN** the user holds personal tokens and no OAuth grant
- **THEN** the Connected apps section shows the empty state and the personal tokens stay in their own table

### Requirement: Disconnect revokes the grant
Posting *Disconnect* with an application id SHALL revoke every refresh token of the user for that
application (the toolkit's `revoke()`, which revokes their access tokens), mark any remaining live
access-token profile `revoked_at`, write `AuditLog(action="oauth_disconnect")` with `client_id` and
`application_id`, emit `oauth_app_disconnected` (application id, scopes; no name), and redirect back
to the page; the next API call with any of those tokens SHALL be `401` and the next refresh
`invalid_grant`. An application id for which the user holds no grant SHALL answer 404 and change
nothing — including another user's grant on the same application.

#### Scenario: Disconnect
- **WHEN** the user posts Disconnect for a connected client
- **THEN** the row disappears, the access token answers `401 invalid_token` on `/api/v1/me`, and the refresh token answers `400 invalid_grant`

#### Scenario: Another user's grant
- **WHEN** user B posts Disconnect with the application id user A is connected to and B is not
- **THEN** the response is 404 and A's tokens still validate

### Requirement: Help and translations
The page "Connect ChatGPT, Claude and other apps" SHALL exist under
`help/src/content/docs/how-to/connect-an-app.md` as a DRAFT (`draft: true`), and the help registry
SHALL NOT carry a `connected_apps` key, until the MCP server (#306) gives creators something to
connect — the key, the link on the connections page and the changelog entry ship with #306. Every
new creator-facing string on the consent page and the connections page SHALL be present in all
catalogs of `TranslationCatalogHygieneTest.TARGET_LOCALES`.

#### Scenario: No link before #306
- **WHEN** the connections page renders with `HELP_SITE_URL` set
- **THEN** it shows no "How to connect an app" link

#### Scenario: Catalogs
- **WHEN** `TranslationCatalogHygieneTest` runs
- **THEN** no consent-page or connected-apps msgid is missing from any target locale

