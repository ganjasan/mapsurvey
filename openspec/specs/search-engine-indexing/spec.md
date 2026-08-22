# search-engine-indexing Specification

## Purpose
TBD - created by archiving change sitemap-excludes-unpublished. Update Purpose after archive.
## Requirements
### Requirement: The sitemap lists only surveys that anonymous visitors can open
`/sitemap.xml` SHALL contain a `<loc>` entry of the form `/surveys/<uuid>/` only for surveys
that satisfy all of: `visibility` in (`public`, `demo`), `status='published'`,
`is_canonical=True`, `published_version` unset, and `deleted_at` unset.

The set of surveys the platform considers publicly visible SHALL be computed by a single
function used by both the landing page and the sitemap. Neither consumer SHALL re-express or
narrow that filter.

#### Scenario: A draft survey is not advertised
- **GIVEN** a survey with `visibility='public'` and `status='draft'`
- **WHEN** `/sitemap.xml` is fetched
- **THEN** the response SHALL NOT contain that survey's UUID

#### Scenario: A closed or archived survey is not advertised
- **GIVEN** a survey with `visibility='public'` and `status` in (`closed`, `archived`)
- **WHEN** `/sitemap.xml` is fetched
- **THEN** the response SHALL NOT contain that survey's UUID

#### Scenario: A non-canonical version header is not advertised
- **GIVEN** a survey with `visibility='public'` and `is_canonical=False`
- **WHEN** `/sitemap.xml` is fetched
- **THEN** the response SHALL NOT contain that survey's UUID

#### Scenario: A canonical survey superseded by a published version is not advertised
- **GIVEN** a canonical survey with `visibility='public'` and `published_version` set
- **WHEN** `/sitemap.xml` is fetched
- **THEN** the response SHALL NOT contain that survey's UUID

#### Scenario: A published survey is advertised
- **GIVEN** a canonical survey with `visibility='public'`, `status='published'`, no
  `published_version` and no `deleted_at`
- **WHEN** `/sitemap.xml` is fetched
- **THEN** the response SHALL contain `/surveys/<uuid>/` for that survey

#### Scenario: Every advertised survey URL is reachable
- **WHEN** `/sitemap.xml` is fetched and each `/surveys/<uuid>/` entry is requested anonymously
- **THEN** no entry SHALL respond with `404`

### Requirement: Unpublished surveys are not indexable
The platform SHALL set `X-Robots-Tag: noindex` on any response to `/surveys/<survey_slug>/`
for a survey whose `status` is not `published`. This SHALL apply regardless of the survey's
`visibility`, and regardless of whether the response is the survey, a redirect, a password
gate, or an unavailable page.

A `published` survey SHALL NOT carry that header.

#### Scenario: A private draft reached by external link is not indexable
- **GIVEN** a survey with `visibility='private'` and `status='draft'`
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/`
- **THEN** the response SHALL carry `X-Robots-Tag: noindex`

#### Scenario: A testing survey is not indexable
- **GIVEN** a survey with `status='testing'` and no password
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/`
- **THEN** the response SHALL carry `X-Robots-Tag: noindex`

#### Scenario: A published survey is indexable
- **GIVEN** a canonical survey with `visibility='public'` and `status='published'`
- **WHEN** an anonymous visitor requests `/surveys/<uuid>/`
- **THEN** the response SHALL NOT carry `X-Robots-Tag: noindex`

