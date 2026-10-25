## ADDED Requirements

### Requirement: Share information
The API SHALL offer `GET /surveys/{uuid}/share` (scope `surveys:read`, role `viewer`) returning the
survey's `status` and `shareable` (true only when published). When shareable it SHALL return the
respondent URL, the embed snippet the Share page shows, the allowed embed hosts, and the public
results URL when that page is published. When the survey is in testing it SHALL return the test link
with its token to callers with the `editor` role or above, and to nobody else. URLs SHALL be built on
`SITE_URL`, the same way the editor builds them.

#### Scenario: Published survey
- **WHEN** a viewer's token asks for a published survey's share information
- **THEN** it gets `shareable: true`, the URL `<SITE_URL>/surveys/<uuid>/`, the embed snippet and the hosts

#### Scenario: Testing survey and the test link
- **WHEN** an editor and then a viewer ask for a testing survey's share information
- **THEN** the editor's answer carries `test_url` with `?token=` and the viewer's has `test_url: null`; both have `shareable: false`

### Requirement: QR code of a survey link
The API SHALL offer `GET /surveys/{uuid}/share/qr.svg` and `qr.png` (scope `surveys:read`) drawing
the respondent URL as a QR code on the server, with `size` (pixels per module, 1–40, default 10)
and optional `link` (a tracked link id of the survey, whose URL is drawn instead). A survey that is
not shareable SHALL answer `409 not_shareable`.

#### Scenario: PNG of the survey link
- **WHEN** `qr.png` is requested for a published survey
- **THEN** the response is `image/png` and decodes to the respondent URL

#### Scenario: Draft
- **WHEN** a QR is requested for a draft survey
- **THEN** the response is `409 not_shareable`

### Requirement: Tracked links over the API
The API SHALL list (`surveys:read`), create and delete (`surveys:write`, role `editor`) a survey's
tracked links on its canonical survey, each with `utm_source` (required), `utm_medium`,
`utm_campaign` (each at most 100 characters), its URL, and the responses `started` and `completed`
through it, counted the way the Responses page's traffic sources count them. A survey SHALL hold at
most 200 tracked links (`409 limit_reached` beyond). Creating and deleting SHALL be audited.

#### Scenario: Create and count
- **WHEN** an editor creates a link `utm_source=flyer` and one response then starts with those parameters
- **THEN** the list shows the link with its URL carrying `utm_source=flyer` and `started: 1`

#### Scenario: Viewer cannot create
- **WHEN** a viewer's token posts a tracked link
- **THEN** the response is `403 forbidden_role`

### Requirement: Embed hosts over the API
The API SHALL offer `PUT /surveys/{uuid}/share/embed-hosts` with `{"hosts": [...]}` (scope
`surveys:write`, role `editor`), validating through the editor's host rules; an invalid entry SHALL
answer `400 validation` naming it, an empty list SHALL mean any site, and the change SHALL be saved
on the canonical survey and audited.

#### Scenario: Invalid host
- **WHEN** the hosts are `["example.org", "not a host!"]`
- **THEN** the response is 400 naming `not a host!` and nothing is saved

### Requirement: Links the editor builds use the public base
The Share page's tracked-link URLs SHALL be built on the same public base as its respondent link,
never on `request.scheme`, so they are `https` behind the proxy; and tracked links SHALL belong to the
canonical survey whichever version the page was opened on.

#### Scenario: Behind the proxy
- **WHEN** the Share page renders behind a proxy that sends `X-Forwarded-Proto: https`
- **THEN** every tracked link starts with `https://`
