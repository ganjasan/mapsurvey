## ADDED Requirements

### Requirement: FAQ section on SEO landing pages
Each SEO landing page SHALL render a visible FAQ section built from a per-page, ordered list of 3–5 question/answer pairs. Questions SHALL be specific to that page's intent; competitor-comparison pages (`alternatives/*`) SHALL include comparison-specific questions.

#### Scenario: FAQ section rendered on a landing page
- **WHEN** an anonymous visitor loads any SEO landing page (e.g. `/civic-engagement/`)
- **THEN** the HTML SHALL contain an FAQ section with each question text and its answer text visible

#### Scenario: Page-specific questions
- **WHEN** two different landing pages are compared (e.g. `/participatory-budgeting/` and `/alternatives/maptionnaire/`)
- **THEN** their FAQ question sets SHALL NOT be identical

#### Scenario: FAQ is optional per page
- **WHEN** a template extends `base_landing.html` without providing an FAQ list
- **THEN** the page SHALL render with no FAQ section and no `FAQPage` JSON-LD, and SHALL NOT error

### Requirement: FAQPage structured data
Each SEO landing page that renders an FAQ section SHALL emit one `FAQPage` JSON-LD script whose questions and answers are derived from the same per-page list used for the visible FAQ, so the two cannot drift.

#### Scenario: FAQPage JSON-LD present and valid
- **WHEN** a landing page with an FAQ is loaded
- **THEN** the HTML SHALL contain a `<script type="application/ld+json">` with `"@type": "FAQPage"`
- **AND** the script content SHALL parse as valid JSON
- **AND** each `mainEntity` question `name` SHALL match a question shown in the visible FAQ section

#### Scenario: Answer text is JSON-safe
- **WHEN** an FAQ answer contains quotes or apostrophes
- **THEN** the emitted `FAQPage` JSON-LD SHALL still parse as valid JSON

### Requirement: BreadcrumbList structured data
Each SEO landing page SHALL emit a `BreadcrumbList` JSON-LD describing its position in the site hierarchy. Audience/keyword pages SHALL use `Home › <Page>`; competitor pages SHALL use `Home › Alternatives › <Page>`.

#### Scenario: Breadcrumb on a single-level landing
- **WHEN** `/for-planners/` is loaded
- **THEN** the HTML SHALL contain a `<script type="application/ld+json">` with `"@type": "BreadcrumbList"` whose items are Home then the page, with absolute `item` URLs

#### Scenario: Breadcrumb on a two-level alternatives page
- **WHEN** `/alternatives/maptionnaire/` is loaded
- **THEN** the `BreadcrumbList` SHALL contain three ordered items: Home, Alternatives, and the page, with `position` 1, 2, 3

### Requirement: Opt-in structured-data block in base landing template
`base_landing.html` SHALL expose a `structured_data` template block, rendered after the site-wide `SoftwareApplication` and `Organization` JSON-LD, into which landing pages inject their per-page structured data.

#### Scenario: Site-wide markup preserved
- **WHEN** any page extending `base_landing.html` is loaded
- **THEN** the site-wide `SoftwareApplication` and `Organization` JSON-LD SHALL still be present regardless of whether the page supplies per-page structured data

### Requirement: Single source of truth for SEO landing URLs
The system SHALL define the set of SEO landing paths (with `changefreq`, `priority`, and `lastmod`) in one registry. `robots.txt` and `sitemap.xml` SHALL both derive their SEO-landing entries from that registry.

#### Scenario: Sitemap lists every registered landing
- **WHEN** `/sitemap.xml` is requested
- **THEN** for every path in the registry there SHALL be a matching `<url><loc>` entry
- **AND** each landing entry SHALL include `<lastmod>`, `<changefreq>`, and `<priority>`

#### Scenario: Robots allows every registered landing
- **WHEN** `/robots.txt` is requested
- **THEN** every registry path SHALL be covered by an `Allow:` rule

#### Scenario: Registry and routes stay in sync
- **WHEN** the test suite runs
- **THEN** every registered landing path SHALL resolve to a view
- **AND** every SEO landing route SHALL be present in the registry
