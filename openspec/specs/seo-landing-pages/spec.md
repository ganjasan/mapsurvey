# seo-landing-pages Specification

## Purpose
TBD - created by archiving change seo-engagement-landings. Update Purpose after archive.
## Requirements
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

### Requirement: Civic engagement category page
The system SHALL serve a public category page at `/civic-engagement/` targeting the
`civic engagement` / `civic involvement` search cluster.

#### Scenario: Page renders with head-term positioning
- **WHEN** any visitor navigates to `/civic-engagement/`
- **THEN** the system responds `200` with a page extending `base_landing.html` whose visible H1 contains "civic engagement"
- **AND** the `<link rel="canonical">` points to `https://mapsurvey.org/civic-engagement/`

#### Scenario: Funnel links downward
- **WHEN** the page is rendered
- **THEN** it SHALL link to at least one bottom-funnel product page (`/community-engagement-platform/` or `/public-consultation-software/`)

#### Scenario: UTM-tagged CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA links to registration with `utm_source=civic_engagement`

### Requirement: Participatory budgeting use-case page
The system SHALL serve a public use-case page at `/participatory-budgeting/` targeting the
`participatory budgeting` search term, framed around map-based PB input.

#### Scenario: Page renders with use-case positioning
- **WHEN** any visitor navigates to `/participatory-budgeting/`
- **THEN** the system responds `200` with a page whose visible H1 contains "participatory budgeting"
- **AND** the canonical points to `https://mapsurvey.org/participatory-budgeting/`

#### Scenario: UTM-tagged CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA links to registration with `utm_source=participatory_budgeting`

### Requirement: Consultants audience page
The system SHALL serve a public audience page at `/for-consultants/` for engagement and planning
consultancies, consistent with the existing "for …" audience pages.

#### Scenario: Page renders with audience positioning
- **WHEN** any visitor navigates to `/for-consultants/`
- **THEN** the system responds `200` with consultant-focused positioning and canonical `https://mapsurvey.org/for-consultants/`

#### Scenario: UTM-tagged CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA links to registration with `utm_source=consultants`

#### Scenario: Present in the Solutions nav dropdown
- **WHEN** any page extending `base_landing.html` is rendered
- **THEN** the nav "Solutions" dropdown SHALL include a link to `/for-consultants/`

### Requirement: Social Pinpoint comparison page
The system SHALL serve a public comparison page at `/alternatives/social-pinpoint/` following the
`maptionnaire_alternative` pattern, including a "being fair" section.

#### Scenario: Page renders with comparison positioning
- **WHEN** any visitor navigates to `/alternatives/social-pinpoint/`
- **THEN** the system responds `200` with "Social Pinpoint alternative" positioning and canonical `https://mapsurvey.org/alternatives/social-pinpoint/`

#### Scenario: Factual accuracy of competitor claims
- **WHEN** the page states competitor limitations
- **THEN** claims SHALL match the verified dossier (e.g. "the current-generation Social Map limits respondents to point markers" — not "cannot do lines") and include a "when they may fit better" section

#### Scenario: UTM-tagged CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA carries `utm_source=comparison` with `utm_medium=social_pinpoint_alt`

### Requirement: MetroQuest comparison page
The system SHALL serve a public comparison page at `/alternatives/metroquest/` targeting customers
of the sunset MetroQuest product searching for a replacement.

#### Scenario: Page renders with migration positioning
- **WHEN** any visitor navigates to `/alternatives/metroquest/`
- **THEN** the system responds `200` with "MetroQuest alternative" positioning and canonical `https://mapsurvey.org/alternatives/metroquest/`

#### Scenario: UTM-tagged CTA
- **WHEN** the page is rendered
- **THEN** the primary CTA carries `utm_source=comparison` with `utm_medium=metroquest_alt`

### Requirement: Wave-2 pages are discoverable
All five wave-2 pages SHALL be discoverable by search engines.

#### Scenario: Listed in sitemap
- **WHEN** `/sitemap.xml` is fetched
- **THEN** it contains `/civic-engagement/`, `/participatory-budgeting/`, `/for-consultants/`, `/alternatives/social-pinpoint/`, and `/alternatives/metroquest/`

#### Scenario: Allowed in robots
- **WHEN** `/robots.txt` is fetched
- **THEN** `/civic-engagement/`, `/participatory-budgeting/`, and `/for-consultants/` are explicitly allowed (the `/alternatives/` prefix is already allowed)

#### Scenario: Linked from shared footer
- **WHEN** any page extending `base_landing.html` is rendered
- **THEN** the footer "Product" list includes links to all five wave-2 pages

