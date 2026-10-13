# survey-oembed Specification

## Purpose
TBD - created by archiving change embed-surveys. Update Purpose after archive.
## Requirements
### Requirement: oEmbed endpoint describes an embeddable survey
The system SHALL serve `GET /oembed/` taking `url` (required), `format` (`json` by default),
`maxwidth` and `maxheight`. When `url` is a survey entry URL on this site
(`/surveys/<uuid>/`, any query string ignored) for a survey that an anonymous visitor may open
(published, not held for review, no password), the response SHALL be
`application/json` with `version: "1.0"`, `type: "rich"`, `title` (the survey name),
`provider_name: "Mapsurvey"`, `provider_url`, `html` (the Share page's iframe with `width`
and `height` attributes and WITHOUT the `embed.js` script tag: Iframely, which Notion and
others embed through, discards an oEmbed html that contains a script), `width`, `height` and
`cache_age: 3600`.
`width` SHALL default to 100 % expressed as the pixel value 800 and `height` to 720, each
clamped to `maxwidth`/`maxheight` when given. The response SHALL carry
`Access-Control-Allow-Origin: *`. Any other `url` — another host, a non-survey path, an unknown
UUID, a draft, testing, closed, held or password-protected survey — SHALL return 404 with no
survey data. `format=xml` SHALL return 501.

#### Scenario: Published survey resolves
- **WHEN** `/oembed/?url=https://<host>/surveys/<uuid>/&format=json` is requested for a published survey
- **THEN** the response is 200 JSON with `type: "rich"`, `title` equal to the survey name and `html` containing `/surveys/<uuid>/?embed=1`

#### Scenario: Max dimensions are honoured
- **WHEN** the request adds `maxwidth=600&maxheight=500`
- **THEN** `width` is 600, `height` is 500 and the `html` iframe uses those values

#### Scenario: Unpublished survey is not described
- **WHEN** the endpoint is called with the URL of a draft, testing or closed survey
- **THEN** the response is 404 and the body contains neither the survey name nor its UUID

#### Scenario: Foreign URL is refused
- **WHEN** the endpoint is called with `url=https://other.example/surveys/<uuid>/`
- **THEN** the response is 404

#### Scenario: XML is not offered
- **WHEN** the endpoint is called with `format=xml`
- **THEN** the response is 501

### Requirement: Survey entry page advertises oEmbed discovery
The HTML of the survey entry page and its sections for an anonymously openable survey SHALL
contain `<link rel="alternate" type="application/json+oembed" href="<absolute oembed URL for
this survey>" title="<survey name>">`. Surveys that the endpoint would refuse SHALL NOT carry
the link.

#### Scenario: Discovery link present on a published survey
- **WHEN** the first section of a published, password-free survey is rendered
- **THEN** the `<head>` contains the oEmbed discovery link pointing at `/oembed/?url=…&format=json`

#### Scenario: No discovery link on a password-protected survey
- **WHEN** a section of a published survey with a password is rendered
- **THEN** the `<head>` contains no `application/json+oembed` link

