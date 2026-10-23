## MODIFIED Requirements

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
`X-Frame-Options: SAMEORIGIN`. Responses under `/oauth/` SHALL carry `X-Frame-Options: DENY`
and `frame-ancestors 'none'` (set by `api.middleware.OAuthResponseHeadersMiddleware`), and the
embed middleware SHALL never find such a request marked embeddable.

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

#### Scenario: OAuth consent page is never framed
- **WHEN** a signed-in user requests a valid `/oauth/authorize/` URL with the full middleware stack
- **THEN** the response carries `X-Frame-Options: DENY` and `Content-Security-Policy: frame-ancestors 'none'`, and `request.survey_frame_ancestors` was never set

#### Scenario: A draft stays unframeable
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/` for a draft survey
- **THEN** the 404 response carries `X-Frame-Options: SAMEORIGIN`

#### Scenario: Closed survey page is framable
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/` for a closed survey
- **THEN** the closed page response carries a `frame-ancestors` directive and no `X-Frame-Options`
