## ADDED Requirements

### Requirement: Competitor data model
The system SHALL represent each competitor as a database row containing a unique slug, a human-readable display name, and a flag indicating whether the competitor is visible in the hub.

#### Scenario: Competitor with unique slug
- **WHEN** a new `Competitor` row is created with slug "maptionnaire"
- **THEN** the system SHALL persist it and reject any subsequent `Competitor` insert with the same slug

#### Scenario: Inactive competitor hidden from hub
- **WHEN** a `Competitor` row has `is_active=False`
- **AND** any visitor requests `/alternatives/`
- **THEN** the hub page SHALL NOT render a card for that competitor

### Requirement: Per-page publication status
The system SHALL track publication status for each combination of competitor and page type (`alternative`, `vs`, `migrate`) as a separate row with status `draft` or `published`.

#### Scenario: Unique competitor/page-type pair
- **WHEN** a `ComparisonPage` row exists for (`maptionnaire`, `alternative`)
- **THEN** the system SHALL reject a second `ComparisonPage` insert with the same pair

#### Scenario: Draft as default status
- **WHEN** a new `ComparisonPage` row is created without an explicit status
- **THEN** the row SHALL persist with `status='draft'`

### Requirement: Fact-check date tracking
Each `ComparisonPage` SHALL store a `last_fact_checked` date updated when content has been verified against the competitor's current public information.

#### Scenario: Display on rendered page
- **WHEN** a comparison page is rendered for any visitor
- **THEN** the page SHALL display "Comparison information current as of {month} {year}" where the date is formatted from `last_fact_checked`

### Requirement: Hub page at `/alternatives/`
The system SHALL serve a public hub page at `/alternatives/` listing every active competitor with links to each competitor's published comparison pages.

#### Scenario: Anonymous visitor sees only published pages
- **WHEN** an unauthenticated visitor GETs `/alternatives/`
- **AND** competitor "maptionnaire" has `alternative` page published but `vs` and `migrate` pages in draft
- **THEN** the hub SHALL display the Maptionnaire card with a link to `/alternatives/maptionnaire/` only

#### Scenario: Staff visitor sees draft pages labelled
- **WHEN** an authenticated staff user GETs `/alternatives/`
- **AND** competitor "maptionnaire" has one page published and two in draft
- **THEN** the hub SHALL display all three links with a "Draft" label on the unpublished ones

#### Scenario: Competitor with no published pages hidden from anonymous
- **WHEN** an unauthenticated visitor GETs `/alternatives/`
- **AND** competitor "metroquest" is active but all its `ComparisonPage` rows are in draft
- **THEN** the MetroQuest card SHALL NOT appear in the rendered hub

### Requirement: Per-competitor comparison URLs
The system SHALL serve three URLs per competitor: `/alternatives/<slug>/`, `/vs/<slug>/`, and `/migrate-from-<slug>/`, each rendering a distinct template with its own canonical URL.

#### Scenario: Published page accessible to anonymous
- **WHEN** `ComparisonPage(competitor=maptionnaire, page_type=alternative, status=published)` exists
- **AND** an unauthenticated visitor GETs `/alternatives/maptionnaire/`
- **THEN** the system SHALL return HTTP 200 with the rendered template `comparisons/maptionnaire/alternative.html`

#### Scenario: Draft page 404 for anonymous
- **WHEN** `ComparisonPage(competitor=maptionnaire, page_type=vs, status=draft)` exists
- **AND** an unauthenticated visitor GETs `/vs/maptionnaire/`
- **THEN** the system SHALL return HTTP 404

#### Scenario: Draft page accessible to staff
- **WHEN** `ComparisonPage(competitor=maptionnaire, page_type=migrate, status=draft)` exists
- **AND** a staff user GETs `/migrate-from-maptionnaire/`
- **THEN** the system SHALL return HTTP 200 with the draft banner visible in the rendered HTML

#### Scenario: Nonexistent competitor returns 404
- **WHEN** any visitor GETs `/alternatives/nonexistent-slug/`
- **AND** no matching `ComparisonPage` row exists
- **THEN** the system SHALL return HTTP 404

### Requirement: Staff draft preview banner
When a draft page is served to a staff user, the rendered page SHALL display a visually distinct banner warning that the content is not yet published.

#### Scenario: Banner visible for staff on draft
- **WHEN** a staff user views a draft comparison page
- **THEN** the HTML SHALL contain an element with class `draft-banner` displaying text indicating draft status

#### Scenario: Banner hidden on published page
- **WHEN** any user views a published comparison page
- **THEN** the HTML SHALL NOT contain the `draft-banner` element

### Requirement: Legal disclaimer on every comparison page
Every comparison page SHALL render a trademark disclaimer and non-affiliation statement identifying the competitor's trademark holder, and SHALL display the `last_fact_checked` date.

#### Scenario: Disclaimer present on all page types
- **WHEN** any visitor views `/alternatives/maptionnaire/`, `/vs/maptionnaire/`, or `/migrate-from-maptionnaire/`
- **THEN** the HTML SHALL contain text identifying Maptionnaire as a trademark of Mapita Oy and asserting that Mapsurvey is not affiliated with Mapita Oy

#### Scenario: Fact-check date shown
- **WHEN** any visitor views a comparison page where `last_fact_checked='2026-04-18'`
- **THEN** the rendered HTML SHALL contain the text "April 2026"

### Requirement: Published pages included in sitemap
The system SHALL include URLs of all published comparison pages in `/sitemap.xml`.

#### Scenario: Published page in sitemap
- **WHEN** `ComparisonPage(competitor=maptionnaire, page_type=alternative, status=published)` exists
- **AND** a crawler GETs `/sitemap.xml`
- **THEN** the response SHALL contain the URL `/alternatives/maptionnaire/`

#### Scenario: Draft page excluded from sitemap
- **WHEN** `ComparisonPage(competitor=maptionnaire, page_type=vs, status=draft)` exists
- **AND** a crawler GETs `/sitemap.xml`
- **THEN** the response SHALL NOT contain the URL `/vs/maptionnaire/`

#### Scenario: Hub always in sitemap
- **WHEN** a crawler GETs `/sitemap.xml`
- **THEN** the response SHALL contain the URL `/alternatives/` regardless of any `ComparisonPage` states

### Requirement: English-only rendering
All comparison pages SHALL render in English regardless of the visitor's session language.

#### Scenario: Russian session still sees English
- **WHEN** a visitor with `django_language='ru'` in session GETs `/alternatives/maptionnaire/`
- **THEN** the rendered page SHALL display English content

### Requirement: Admin-controlled status transitions
Status changes between `draft` and `published` SHALL be performable through Django admin without requiring a code deploy.

#### Scenario: Admin flips draft to published
- **WHEN** a staff user edits a `ComparisonPage` row in Django admin
- **AND** changes `status` from `draft` to `published`
- **AND** saves the change
- **THEN** the corresponding URL SHALL immediately return HTTP 200 to anonymous visitors without server restart

### Requirement: SEO meta tags per page
Each comparison page SHALL override `meta_description`, `meta_keywords`, `canonical_url`, `og_url`, and `og_title` blocks from `base_landing.html` with page-specific values targeting each page's search intent.

#### Scenario: Unique meta description per URL
- **WHEN** any visitor views `/alternatives/maptionnaire/` and `/vs/maptionnaire/`
- **THEN** the two pages SHALL have distinct `<meta name="description">` contents
