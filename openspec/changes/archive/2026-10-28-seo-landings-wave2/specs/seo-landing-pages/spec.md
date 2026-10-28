## ADDED Requirements

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
