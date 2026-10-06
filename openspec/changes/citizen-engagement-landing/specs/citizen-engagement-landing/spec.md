## ADDED Requirements

### Requirement: Citizen engagement platform page carries the category contract
The page `/citizen-engagement-platform/` SHALL be a category landing in the `seo_landings` registry and SHALL contain, in this order: a hero whose H1 is "Citizen Engagement Platform", a definition section naming the head term and its variants ("citizen participation platform", "citizen engagement software for local government") in prose, a how-it-works walk-through with the four product screenshots, a feature grid, a comparison table against Go Vocal and Citizen Space followed by a dated note and a "when they may fit better" note, a procurement section, a use-case list, the shared pricing section, the shared sibling-links section, the "From the field" block and the FAQ. Its visible copy SHALL be at least 1,500 words.

#### Scenario: Page renders the contract
- **WHEN** `/citizen-engagement-platform/` is rendered
- **THEN** it returns 200 with an H1 "Citizen Engagement Platform", a comparison table naming Go Vocal and Citizen Space, a note dated "as of October 2026", the four screenshot files from `img/landing/`, the pricing section with "$49", "$490" and a link to `/pro/`, the sibling links to the four other category pages and to `/for-government/`, and at least 1,500 visible words

#### Scenario: Registry drives sitemap and robots
- **WHEN** `/sitemap.xml` and `/robots.txt` are fetched
- **THEN** the sitemap lists `/citizen-engagement-platform/` with `<lastmod>2026-10-06</lastmod>` and robots carries `Allow: /citizen-engagement-platform/`

### Requirement: Procurement questions are answered on the page
The page SHALL contain a procurement section and FAQ entries answering, in the buyer's words, whether there is a free plan or trial for governments, what the platform costs a small jurisdiction, who owns the collected data and how it exports, and what the uptime and support arrangements are. The uptime copy SHALL NOT state an uptime percentage or an SLA.

#### Scenario: FAQ names the four procurement questions
- **WHEN** the registry FAQ of `citizen_engagement_platform` is read
- **THEN** it contains a question about a free trial or free plan, a question about the cost for a small jurisdiction, a question about data ownership or export, and a question about uptime, and the uptime answer contains no percentage sign

### Requirement: No competitor price figures on any landing
No landing template in the `seo_landings` registry and no registry FAQ answer SHALL contain a currency figure for another vendor; a competitor's pricing cell SHALL state the pricing model (per instance, per licence, per project, quote only), whether a free tier or trial exists, and whether the rate is listed publicly (for example on UK G-Cloud) or available from sales only. The only currency figures on a landing SHALL be Mapsurvey's own.

#### Scenario: Templates and FAQ carry only our own figures
- **WHEN** every template named in the registry and every registry FAQ answer is read
- **THEN** the only currency figures found are $0, $49 and $490

#### Scenario: Competitor pricing cell states the model
- **WHEN** `/community-engagement-platform/`, `/civic-engagement/` or `/public-consultation-software/` is rendered
- **THEN** each competitor's pricing cell says "Quote only" and names where the rate is listed or that none is published

### Requirement: Three pages, three intents
The citizen page SHALL state in its definition section that the community engagement platform page describes the category and product and the civic engagement page describes methods, linking to both; the community and civic pages SHALL each link to `/citizen-engagement-platform/` in their body copy; the shared sibling partial SHALL list the citizen page on the other four category pages and never on itself.

#### Scenario: Cross-links in body copy
- **WHEN** `/community-engagement-platform/` and `/civic-engagement/` are rendered
- **THEN** each contains a link to `/citizen-engagement-platform/` outside the sibling block, and `/citizen-engagement-platform/` links to both in its definition section

#### Scenario: Sibling block excludes itself
- **WHEN** `/citizen-engagement-platform/` is rendered
- **THEN** the block under `id="related"` links to the four other category pages and `/for-government/` and not to `/citizen-engagement-platform/`

### Requirement: Story topic binding
The `citizen-engagement` topic SHALL resolve to the `citizen_engagement_platform` landing, so that a story carrying it renders in the page's "From the field" block and its chip links to the page.

#### Scenario: Tagged story appears on the page
- **WHEN** a published story has topics `["citizen-engagement"]` and `/citizen-engagement-platform/` is rendered
- **THEN** the page contains the story's title inside the `id="from-the-field"` block
