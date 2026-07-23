## ADDED Requirements

### Requirement: Community engagement platform landing page
The system SHALL serve a public product landing page at `/community-engagement-platform/` for all
visitors (anonymous and authenticated), targeting the `community engagement platform` search term.

#### Scenario: Page renders for anonymous visitor
- **WHEN** an unauthenticated user navigates to `/community-engagement-platform/`
- **THEN** the system responds `200` and renders a page extending `base_landing.html`
- **AND** the page SHALL NOT redirect to `/accounts/login/`

#### Scenario: Head-term positioning in the H1
- **WHEN** the page is rendered
- **THEN** the visible H1 SHALL present the product as a "community engagement platform" (the head term, not scoped to a single audience)

#### Scenario: Self-referential canonical
- **WHEN** the page is rendered
- **THEN** the `<link rel="canonical">` SHALL point to `https://mapsurvey.org/community-engagement-platform/`

#### Scenario: UTM-tagged registration CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA links to registration with `utm_source=engagement_platform`

#### Scenario: Cross-links to audience pages
- **WHEN** the page is rendered
- **THEN** it SHALL link to at least one audience page (`/for-government/` or `/for-planners/`) so the product page and audience pages reinforce each other

### Requirement: Public consultation software landing page
The system SHALL serve a public product landing page at `/public-consultation-software/` for all
visitors (anonymous and authenticated), targeting the `public consultation software` search term.

#### Scenario: Page renders for anonymous visitor
- **WHEN** an unauthenticated user navigates to `/public-consultation-software/`
- **THEN** the system responds `200` and renders a page extending `base_landing.html`
- **AND** the page SHALL NOT redirect to `/accounts/login/`

#### Scenario: Consultation-workflow positioning in the H1
- **WHEN** the page is rendered
- **THEN** the visible H1 SHALL present the product as "public consultation software"

#### Scenario: Self-referential canonical
- **WHEN** the page is rendered
- **THEN** the `<link rel="canonical">` SHALL point to `https://mapsurvey.org/public-consultation-software/`

#### Scenario: UTM-tagged registration CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA links to registration with `utm_source=consultation_software`

### Requirement: First-touch source capture on product landing pages
Each product landing page SHALL record the visitor's first-touch acquisition source, consistent with
the existing audience landing pages.

#### Scenario: Source captured on first view
- **WHEN** a visitor first lands on a product landing page
- **THEN** the view SHALL call `capture_signup_source` so a later registration is attributed

### Requirement: Product landing pages are discoverable
Both product landing pages SHALL be discoverable by search engines through the site's sitemap and
robots directives.

#### Scenario: Listed in sitemap
- **WHEN** `/sitemap.xml` is fetched
- **THEN** it SHALL contain `/community-engagement-platform/` and `/public-consultation-software/`

#### Scenario: Allowed in robots
- **WHEN** `/robots.txt` is fetched
- **THEN** it SHALL allow `/community-engagement-platform/` and `/public-consultation-software/`

#### Scenario: Linked from shared footer
- **WHEN** any page extending `base_landing.html` is rendered
- **THEN** the footer "Product" list SHALL include links to both product landing pages
