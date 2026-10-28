## ADDED Requirements

### Requirement: Category landing content contract
Each of the four category landing pages — `/community-engagement-platform/`, `/civic-engagement/`, `/public-consultation-software/`, `/participatory-budgeting/` — SHALL contain, in this order: a hero whose H1 is the page's head term, a definition section naming the head term and its close variants in prose, a how-it-works walk-through with product screenshots, a feature grid, a comparison table against two named incumbents of that category followed by a "when they may fit better" note, a use-case list, the shared pricing section, the shared sibling-links section, the "From the field" block and the FAQ. The visible copy of each page (markup, scripts, styles, navigation and footer excluded) SHALL be at least 1,500 words.

#### Scenario: Community engagement platform page
- **WHEN** `/community-engagement-platform/` is rendered
- **THEN** it contains an H1 "Community Engagement Platform", a comparison table naming Social Pinpoint and EngagementHQ, the four screenshot files from `img/landing/`, the pricing section, the sibling links and a FAQ, and its visible text is at least 1,500 words

#### Scenario: Public consultation software page
- **WHEN** `/public-consultation-software/` is rendered
- **THEN** it contains an H1 "Public Consultation Software", a comparison table naming Citizen Space and Commonplace, the pricing section, the sibling links and at least 1,500 words of visible text

#### Scenario: Civic engagement page
- **WHEN** `/civic-engagement/` is rendered
- **THEN** it contains an H1 naming civic engagement, a comparison table naming Go Vocal and Consul, the pricing section, the sibling links and at least 1,500 words of visible text

#### Scenario: Participatory budgeting page
- **WHEN** `/participatory-budgeting/` is rendered
- **THEN** it contains an H1 naming participatory budgeting, a comparison table naming Decidim and Balancing Act, a sentence stating that Mapsurvey collects the location side and is not a budget-allocation or voting module, the pricing section, the sibling links and at least 1,500 words of visible text

### Requirement: Comparison tables state their date and source
Every comparison table on a category landing SHALL be followed by a note that its competitor details reflect the vendors' published pages as of a named month, and a cell for a fact the vendor does not publish SHALL say so rather than assert a value.

#### Scenario: Dated note under the table
- **WHEN** any of the four category pages is rendered
- **THEN** the text following its comparison table names the month and year the vendor pages were read

### Requirement: Shared pricing section
The four category pages SHALL include one shared pricing partial showing a Free plan at $0 and a Pro plan at $49 per month or $490 per year per workspace with unlimited users, surveys and responses; the Pro plan SHALL link to `/pro/` and SHALL be labelled as early access. The figures SHALL appear in the partial only, never in page templates.

#### Scenario: Prices on every category page
- **WHEN** any of the four category pages is rendered
- **THEN** it contains "$49", "$490" and a link to `/pro/`

#### Scenario: Price lives in one file
- **WHEN** the four category templates are read
- **THEN** none of them contains the string "$49"

### Requirement: Sibling links
Each category page SHALL link to the other three category pages and to the audience page that matches it (`/for-government/` for community engagement, public consultation and participatory budgeting; `/for-planners/` for civic engagement), rendered by one shared partial.

#### Scenario: Three siblings plus the audience page
- **WHEN** `/civic-engagement/` is rendered
- **THEN** it links to `/community-engagement-platform/`, `/public-consultation-software/`, `/participatory-budgeting/` and `/for-planners/`, and the sibling block does not link to `/civic-engagement/` itself

### Requirement: No hosting-residency claims on category pages
The four category pages SHALL NOT claim EU hosting, Frankfurt hosting or EU data residency for the hosted service. Where hosting is mentioned, the page SHALL say the hosted service runs in the United States today and that self-hosting is the path to EU residency.

#### Scenario: Community engagement page after the rewrite
- **WHEN** `/community-engagement-platform/` is rendered
- **THEN** it contains neither "EU-hosted" nor "Frankfurt" nor "hosted in the EU", and it contains "United States"

### Requirement: Click-through titles and descriptions
The title of each of the four category pages and of `/alternatives/social-pinpoint/` SHALL start with the page's head term and name a hook (price, free, open source or map drawing) before the brand; the meta description SHALL be at most 160 characters and SHALL name the map input and the price or the free tier.

#### Scenario: Social Pinpoint alternative title
- **WHEN** `/alternatives/social-pinpoint/` is rendered
- **THEN** its `<title>` starts with "Social Pinpoint Alternative" and mentions drawing lines or areas, and its meta description mentions point markers and that pricing is quote-only

#### Scenario: Category page description length
- **WHEN** any of the four category pages is rendered
- **THEN** its meta description is at most 160 characters long

### Requirement: Registry freshness after a content rewrite
When a landing's body is materially rewritten, its registry entry's `lastmod` SHALL be set to the ship date and its FAQ SHALL be rewritten to answer that page's variant queries; the sitemap SHALL reflect the new `lastmod`.

#### Scenario: Sitemap carries the new date
- **WHEN** `/sitemap.xml` is fetched after this change ships
- **THEN** the entries of the four category pages and `/alternatives/social-pinpoint/` carry `<lastmod>2026-10-06</lastmod>`

#### Scenario: FAQ answers a variant query
- **WHEN** `/community-engagement-platform/` is rendered
- **THEN** its FAQ contains a question about the cost of a community engagement platform whose answer names the Pro price, and `/public-consultation-software/` contains a question naming council consultation software
