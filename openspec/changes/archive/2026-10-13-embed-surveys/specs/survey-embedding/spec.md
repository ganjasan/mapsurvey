## ADDED Requirements

### Requirement: Respondent pages may be framed by allowed hosts
Respondent pages SHALL be framable by the hosts a creator allows, as follows.
Every response to a respondent-facing survey route (`/surveys/<slug>/` and everything below
it: the language picker, password gate, sections, uploads, layer GeoJSON and objects, the
thanks page, and the closed and unavailable pages rendered for a resolved survey) SHALL carry
`Content-Security-Policy: frame-ancestors <list>` and SHALL NOT carry `X-Frame-Options`.
The list SHALL always include `'self'`. When the survey's `embed_allowed_hosts` is empty the
list SHALL be `*`; otherwise it SHALL contain `https://<host>` for each entry, with
`*.example.org` rendered as `https://*.example.org`. Responses to any other route, and
responses produced before a survey is resolved (an unknown UUID, a draft's 404), SHALL keep
`X-Frame-Options: SAMEORIGIN`.

#### Scenario: Published survey with no allow-list is framable anywhere
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/` and the first section of a published survey whose `embed_allowed_hosts` is `[]`
- **THEN** each response carries `Content-Security-Policy: frame-ancestors *` and no `X-Frame-Options` header

#### Scenario: Allow-list restricts ancestors
- **GIVEN** a published survey with `embed_allowed_hosts` `["city.example.org", "*.consult.example"]`
- **WHEN** its first section is requested
- **THEN** the response carries `Content-Security-Policy: frame-ancestors 'self' https://city.example.org https://*.consult.example`

#### Scenario: Editor and landing stay unframeable
- **WHEN** `/` and `/editor/surveys/<uuid>/` are requested
- **THEN** each response carries `X-Frame-Options: SAMEORIGIN` and no `frame-ancestors` directive

#### Scenario: A draft stays unframeable
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/` for a draft survey
- **THEN** the 404 response carries `X-Frame-Options: SAMEORIGIN`

#### Scenario: Closed survey page is framable
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/` for a closed survey
- **THEN** the closed page response carries a `frame-ancestors` directive and no `X-Frame-Options`

### Requirement: Session and CSRF cookies survive inside a cross-site frame
The session and CSRF cookies SHALL be usable from inside a cross-site frame.
When the setting `CROSS_SITE_COOKIES` is on (default: on whenever `DEBUG` is off), the
session cookie and the CSRF cookie SHALL be set with `SameSite=None`, `Secure` and
`Partitioned`. When it is off they SHALL keep Django's defaults. No other cookie SHALL be
changed. The CSRF middleware's Origin/Referer verification SHALL remain in force.

#### Scenario: Cookies carry cross-site attributes in production mode
- **WHEN** `CROSS_SITE_COOKIES` is on and a respondent opens a survey section
- **THEN** the `Set-Cookie` header for `sessionid` contains `SameSite=None`, `Secure` and `Partitioned`
- **AND** the `Set-Cookie` header for `csrftoken` contains the same three attributes

#### Scenario: Cookies keep defaults in local development
- **WHEN** `CROSS_SITE_COOKIES` is off and a respondent opens a survey section
- **THEN** the `sessionid` cookie is `SameSite=Lax` and carries neither `Secure` nor `Partitioned`

#### Scenario: Cross-site forgery is still rejected
- **WHEN** a POST to a section URL arrives with a valid session cookie but an `Origin` header naming another site
- **THEN** the response is 403

#### Scenario: A survey completes inside a cross-site frame (end-to-end)
- **GIVEN** a page on a second origin that frames a published two-section survey with the snippet
- **WHEN** a browser answers both sections inside the frame
- **THEN** the answers belong to one `SurveySession` and the frame shows the thanks page

### Requirement: Creators configure embedding from the Share page
The Share page of a published survey SHALL show an Embed section containing the iframe
snippet, a copy control, and an allowed-hosts field. The snippet SHALL reference
`/surveys/<uuid>/?embed=1`, carry `allow="geolocation; fullscreen"`, a `title`, and load
`/embed.js`. The allowed-hosts field SHALL accept one host per line; on save the
system SHALL lower-case entries, strip any scheme, port and path, drop duplicates and blanks,
accept `hostname` or `*.hostname`, reject anything else with a field error, and store the
result on the canonical survey's `embed_allowed_hosts`. The field's help text SHALL say that
platforms embedding from a pasted link (Notion and other Iframely-based consumers verify
`frame-ancestors` from their own servers) need the list left empty. The section SHALL be
available to the `editor` role and above. The copy control SHALL capture `embed_copied` as
specified in `creator-distribution-events`.

#### Scenario: Snippet is shown for a published survey
- **WHEN** an editor opens the Share page of a published survey
- **THEN** the page contains an iframe snippet whose `src` is the survey entry URL with `embed=1`, with `allow="geolocation; fullscreen"`, and a `<script>` tag for `embed.js`

#### Scenario: Snippet is withheld until published
- **WHEN** an editor opens the Share page of a draft or testing survey
- **THEN** no embed snippet is rendered

#### Scenario: Allowed hosts are normalised and saved
- **WHEN** an editor submits the allowed-hosts field with `"https://City.Example.org/projects\n*.consult.example\n\ncity.example.org"`
- **THEN** the canonical survey's `embed_allowed_hosts` becomes `["city.example.org", "*.consult.example"]`

#### Scenario: An invalid host is rejected
- **WHEN** an editor submits the allowed-hosts field with `"not a host"`
- **THEN** the form shows an error and `embed_allowed_hosts` is unchanged

#### Scenario: Hosts are edited on a draft copy
- **GIVEN** a published survey with an open draft copy
- **WHEN** an editor saves allowed hosts from the draft copy's Share page
- **THEN** the value is stored on the published (canonical) survey

### Requirement: Allowed hosts round-trip through export and import
`embed_allowed_hosts` SHALL be written to the survey archive by export and read back by
import. An archive without the key SHALL import as `[]`.

#### Scenario: Export and re-import preserve the list
- **WHEN** a survey with `embed_allowed_hosts` `["city.example.org"]` is exported and imported
- **THEN** the imported survey's `embed_allowed_hosts` is `["city.example.org"]`

#### Scenario: Old archive imports cleanly
- **WHEN** an archive from before this change is imported
- **THEN** the imported survey's `embed_allowed_hosts` is `[]`

### Requirement: Embedded survey reports its height to the host page
An embedded form-layout survey SHALL report its height to the host page.
When the respondent page runs inside a frame (`window.parent !== window`) and the current
section uses the form layout, it SHALL post a message `{mapsurvey: "height", height:
<integer px>}` to the parent (`"*"` target, since the host origin is unknown) on load, after
every HTMX swap and whenever the height changes. The height SHALL be that of the form card
plus its margins, never the document's scroll height (which follows the frame and would
make the frame chase itself). A map-layout section SHALL post nothing and keeps the height
the host gave the frame. `embed.js`, served unhashed at `/embed.js`, SHALL set the `height`
style of the iframe whose `contentWindow` is the message source and SHALL ignore messages of
any other shape. It SHALL NOT act on messages whose source is not one of the page's iframes.

#### Scenario: Form section grows the frame
- **GIVEN** a host page with the snippet and `embed.js`
- **WHEN** the framed survey swaps in a form-layout section taller than 720 px
- **THEN** the iframe's height style becomes that section's document height

#### Scenario: Unrelated messages are ignored
- **WHEN** the host page receives a `message` event `{mapsurvey: "height", height: 9999}` from a window that is not one of its iframes
- **THEN** no iframe height changes

#### Scenario: embed.js is served at a stable path
- **WHEN** `/embed.js` is requested
- **THEN** the response is 200 with a JavaScript content type

### Requirement: Embedded sessions are recognisable in analytics
`session_start` metadata SHALL include `embedded` (boolean) and `embed_host` (string, empty
when not embedded). A session SHALL count as embedded when the entry request carries
`Sec-Fetch-Dest: iframe` with a `Sec-Fetch-Site` other than `same-origin`, or `embed=1` in the
query string. `embed_host` SHALL be the Referer's hostname, lower-cased with a leading `www.`
removed, and empty when there is no Referer. The editor's Live Preview (same-origin frame)
SHALL NOT count as embedded.

#### Scenario: Frame load from another site
- **WHEN** a session starts from a request with `Sec-Fetch-Dest: iframe`, `Sec-Fetch-Site: cross-site` and `Referer: https://www.City.example.org/projects/park`
- **THEN** its `session_start` metadata has `embedded: true` and `embed_host: "city.example.org"`

#### Scenario: Plain link
- **WHEN** a session starts from a top-level navigation
- **THEN** its `session_start` metadata has `embedded: false` and `embed_host: ""`

#### Scenario: Live Preview is not an embed
- **WHEN** a session starts from a request with `Sec-Fetch-Dest: iframe` and `Sec-Fetch-Site: same-origin`
- **THEN** its `session_start` metadata has `embedded: false`

### Requirement: Finishing inside a frame never navigates the frame to a foreign site
A framed respondent SHALL finish on the in-frame thanks page, never on a foreign site.
When the final-section submit comes from a framed document (request header
`MS-Embedded: 1`, set by the respondent page when `window.parent !== window` and the
page is not same-origin with its parent) and the survey's `redirect_url` is a valid absolute
URL, the completion redirect SHALL target the built-in thanks page with `?next=<redirect_url>`
instead of the foreign URL. The thanks page SHALL then render a "Continue" link to that URL
with `target="_top"` and `rel="noopener"`, accepting only an absolute `http(s)` URL equal to
the survey's cleaned `redirect_url` (anything else is ignored). A top-level respondent SHALL
be redirected exactly as before.

#### Scenario: Framed completion goes to the in-frame thanks page
- **GIVEN** a survey whose `redirect_url` is `https://example.com/thanks`
- **WHEN** the last section is submitted via HTMX with `MS-Embedded: 1`
- **THEN** the response carries `HX-Redirect` with the survey's thanks URL and `next=https://example.com/thanks`

#### Scenario: Thanks page offers the continue link
- **WHEN** `/surveys/<uuid>/thanks/?next=https://example.com/thanks` is requested for that survey
- **THEN** the page contains a link to `https://example.com/thanks` with `target="_top"`

#### Scenario: A forged next parameter is ignored
- **WHEN** `/surveys/<uuid>/thanks/?next=https://evil.example/` is requested for a survey whose `redirect_url` is `https://example.com/thanks`
- **THEN** the page contains no link to `https://evil.example/`

#### Scenario: Top-level completion is unchanged
- **WHEN** the last section is submitted via HTMX without `MS-Embedded`
- **THEN** the response carries `HX-Redirect: https://example.com/thanks`

### Requirement: A framed respondent keeps their session without cookies
A framed respondent page SHALL keep its session even when the browser stores no cookies.
Because Safari and every iOS browser store no cookies inside a third-party frame, a respondent
page that is framed by another site (or was reached through a carried session) SHALL carry its
own session key: as a `<meta name="ms-embed-session">` the page's HTMX calls, same-origin
fetches and the upload request send in an `X-MS-Session` header, as a hidden `ms_sid` field in
the language picker and password gate forms, and as a one-time `ms_h` handoff token (valid two
minutes, single use) appended to every redirect the respondent flow issues under `/surveys/`.
The server SHALL honour a carried key only under `/surveys/`, only when no session cookie
arrived, only for a session that exists and is not authenticated, and for a form field only
when the request's `Origin` is this host. CSRF SHALL remain enforced for carried requests: the
CSRF secret the page was rendered with is kept in the session and checked against the form's
token as for any other request. Carried responses SHALL carry `Referrer-Policy: same-origin`.
A respondent whose cookies work SHALL be unaffected.

#### Scenario: Section submitted from a frame without cookies
- **GIVEN** a browser that stored no cookie from the framed first section
- **WHEN** it submits the section via HTMX with `X-MS-Session` set to the key the page carried and the page's CSRF token
- **THEN** the answer is saved to the session that first section created and the next section is returned

#### Scenario: Carried request without the CSRF token is refused
- **WHEN** the same submit arrives with `X-MS-Session` but no CSRF token
- **THEN** the response is 403

#### Scenario: A signed-in session cannot be carried
- **WHEN** a request carries the session key of a signed-in creator's session
- **THEN** the key is ignored and the request is served as an anonymous visitor

#### Scenario: Handoff on the final redirect
- **WHEN** a carried final-section submit returns `HX-Redirect`
- **THEN** the target carries a one-time `ms_h` token, following it serves the thanks page for that session, and a second use of the token carries nothing

#### Scenario: Language picker without cookies
- **WHEN** a framed multilingual survey's language form is posted with the carried `ms_sid` field and a same-host `Origin`
- **THEN** the redirect to the first section carries a handoff and that section renders in the chosen language

#### Scenario: Top-level respondents are unchanged
- **WHEN** a respondent opens a survey outside any frame
- **THEN** the page carries no session meta and redirects carry no handoff token
