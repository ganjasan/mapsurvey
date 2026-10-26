# brand-structured-data Specification

## Purpose
The JSON-LD that tells search engines Mapsurvey is one organisation, one web application and one
site at mapsurvey.org, linked to the profiles we own (change brand-entity, #443).
## Requirements
### Requirement: Every marketing page describes the Mapsurvey organisation and software as one linked entity
Every page rendered from `base_landing.html` SHALL carry JSON-LD with an `Organization` and a
`SoftwareApplication` node. The `Organization` SHALL have `@id` `https://mapsurvey.org/#organization`,
`name` `Mapsurvey`, `url` `https://mapsurvey.org/`, a `logo` and the `sameAs` profiles from the
brand registry. The `SoftwareApplication` SHALL have `@id`
`https://mapsurvey.org/#software`, `name` `Mapsurvey`, `url` `https://mapsurvey.org/`, describe a
hosted web service (`applicationCategory` `BusinessApplication`, `operatingSystem` naming a web
browser) and reference the organisation by `@id` as `publisher` and `author`. Each node SHALL be its own valid JSON-LD document produced from Python data, never assembled
as text in a template.

#### Scenario: Organization and software are linked on a marketing page
- **WHEN** an anonymous visitor requests any `base_landing.html` page, e.g. `/for-planners/`
- **THEN** the page contains JSON-LD nodes of type `Organization` with `@id` `https://mapsurvey.org/#organization` and of type `SoftwareApplication` whose `publisher` is `{"@id": "https://mapsurvey.org/#organization"}`

#### Scenario: The software is not described as a developer tool
- **WHEN** the `SoftwareApplication` node is read from any marketing page
- **THEN** its `applicationCategory` is `BusinessApplication` and its `operatingSystem` does not mention Linux or Docker

### Requirement: The homepage pair names the site for search engines
The homepage (`/`) and its Russian twin (`/ru/`) SHALL carry a `WebSite` JSON-LD node with `@id`
`https://mapsurvey.org/#website`, `name` `Mapsurvey`, `alternateName` including `mapsurvey.org`,
`url` `https://mapsurvey.org/`, and `publisher` referencing the organisation `@id`. Other marketing
pages SHALL NOT carry it.

#### Scenario: Homepage declares the site name
- **WHEN** an anonymous visitor requests `/`
- **THEN** the page contains exactly one `WebSite` node with `name` `Mapsurvey`, an `alternateName` list containing `mapsurvey.org`, and `url` `https://mapsurvey.org/`

#### Scenario: Russian homepage declares the same site
- **WHEN** an anonymous visitor requests `/ru/`
- **THEN** the page contains the same `WebSite` node with `url` `https://mapsurvey.org/`

#### Scenario: Landing pages do not repeat the site node
- **WHEN** an anonymous visitor requests `/for-planners/`
- **THEN** the page contains no `WebSite` node

### Requirement: Brand profiles come from one registry
The URLs in `Organization.sameAs` SHALL come from a single registry in `survey/brand.py`; the
public GitHub repository (`settings.GITHUB_REPO_URL`) SHALL be included when set. Every registry
entry SHALL be an absolute `https://` URL that points off mapsurvey.org, and the list SHALL contain
no duplicates.

#### Scenario: A registry profile appears on the page
- **WHEN** the registry contains `https://participedia.net/method/mapsurvey-1`
- **THEN** that URL appears in `Organization.sameAs` on every marketing page

#### Scenario: A malformed profile fails the suite
- **WHEN** a registry entry is not an absolute `https://` URL, points at mapsurvey.org, or repeats another entry
- **THEN** the brand registry test fails

