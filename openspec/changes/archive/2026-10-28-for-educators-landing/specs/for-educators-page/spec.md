## ADDED Requirements

### Requirement: For-educators landing page
The system SHALL serve a public page at `/for-educators/` positioning Mapsurvey for classroom use
(map-based surveys for student fieldwork), including a classroom case study and assignment ideas.

#### Scenario: Page renders
- **WHEN** an anonymous visitor requests `/for-educators/`
- **THEN** the page returns HTTP 200 with the classroom positioning content

### Requirement: Education-intent SEO
The page SHALL set an education-focused title, meta description, canonical URL, and Open Graph tags,
so it can rank for coursework / participatory-mapping search intent.

#### Scenario: SEO metadata present
- **WHEN** the page is rendered
- **THEN** it includes a canonical/OG URL of `/for-educators/` and an education-oriented title

### Requirement: Discoverable by search engines
The page SHALL be listed in `sitemap.xml` and allowed in `robots.txt`.

#### Scenario: In sitemap and robots
- **WHEN** `sitemap.xml` and `robots.txt` are fetched
- **THEN** both reference `/for-educators/`

### Requirement: UTM-tagged CTAs and source capture
The page's registration CTAs SHALL carry `utm_source=edu` (and a medium identifying the page), and
the page SHALL capture the visitor's first-touch acquisition source, so resulting registrations are
attributed to the education channel.

#### Scenario: CTA carries the education UTM
- **WHEN** the page renders
- **THEN** its registration link includes `utm_source=edu`

#### Scenario: First-touch source captured
- **WHEN** a visitor loads the page (e.g. from a search result)
- **THEN** the acquisition source is captured for attribution at a later registration
