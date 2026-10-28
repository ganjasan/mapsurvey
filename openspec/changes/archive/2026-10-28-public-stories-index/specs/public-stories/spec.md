## ADDED Requirements

### Requirement: Stories index page
The system SHALL serve a public stories index at `/stories/` that lists all published stories as a card grid, ordered by `published_date` descending (unpublished stories excluded). The page SHALL return HTTP 200 even when no stories are published.

#### Scenario: Index lists published stories
- **WHEN** an anonymous visitor requests `/stories/` and published stories exist
- **THEN** the response status SHALL be 200
- **AND** each published story's title SHALL appear with a link to its `stories/<slug>/` detail page

#### Scenario: Draft stories excluded
- **WHEN** `/stories/` is requested and a story has `is_published=False`
- **THEN** that story's title and slug SHALL NOT appear in the response

#### Scenario: Empty state
- **WHEN** `/stories/` is requested and no stories are published
- **THEN** the response status SHALL be 200
- **AND** the page SHALL show an empty-state message rather than an error

### Requirement: Stories index structured data
The stories index SHALL emit a `BreadcrumbList` JSON-LD (`Home › Stories`) and a `CollectionPage` JSON-LD whose `mainEntity` is an `ItemList` of the listed stories.

#### Scenario: Breadcrumb and collection present and valid
- **WHEN** `/stories/` is requested with at least one published story
- **THEN** the HTML SHALL contain a `<script type="application/ld+json">` with `"@type": "BreadcrumbList"` (Home then Stories)
- **AND** a `<script type="application/ld+json">` with `"@type": "CollectionPage"` whose `ItemList` has one entry per listed story
- **AND** every JSON-LD script SHALL parse as valid JSON

### Requirement: Story detail SEO metadata
Each published story detail page SHALL provide a self-referencing `canonical` URL, a `meta_description` derived from the story, and a `BreadcrumbList` JSON-LD (`Home › Stories › <title>`).

#### Scenario: Detail page canonical and breadcrumb
- **WHEN** a published story at `stories/<slug>/` is requested
- **THEN** the HTML SHALL contain a `<link rel="canonical">` whose href ends with `/stories/<slug>/`
- **AND** a `BreadcrumbList` JSON-LD with three ordered items: Home, Stories, and the story title
- **AND** a non-empty `<meta name="description">`

### Requirement: Stories in sitemap
`sitemap.xml` SHALL include the `/stories/` hub and one entry per published story. Unpublished stories SHALL NOT appear.

#### Scenario: Hub and published stories listed
- **WHEN** `/sitemap.xml` is requested and a published story exists
- **THEN** the sitemap SHALL contain a `<loc>` for `/stories/`
- **AND** a `<loc>` for that story's `stories/<slug>/` URL

#### Scenario: Draft story not in sitemap
- **WHEN** `/sitemap.xml` is requested and a story is unpublished
- **THEN** the sitemap SHALL NOT contain that story's `stories/<slug>/` URL

### Requirement: Stories link in landing footer
The landing footer SHALL link to the stories index at `/stories/`.

#### Scenario: Footer links to stories
- **WHEN** any page extending `base_landing.html` is rendered
- **THEN** the footer SHALL contain a link with href `/stories/`
