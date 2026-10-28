## ADDED Requirements

### Requirement: Market guide hub page
The system SHALL serve `/participatory-mapping-tools/` as a landing in the `seo_landings` registry whose H1 names participatory mapping tools and map-based survey and engagement software, containing in order: a hero, a section explaining how to read the guide, one section per category in `CATEGORIES` (what the tools are for, who buys them, the vendors in it), a section explaining each selection criterion in `CRITERIA`, the comparison table, a "where Mapsurvey falls short" block, the per-vendor sources list, a "compare in detail" section linking every `/alternatives/` page, the shared pricing section, the shared sibling links and the FAQ. Its visible copy SHALL be at least 1,500 words.

#### Scenario: Page renders the contract
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** it returns 200 with an H1 containing "Participatory mapping tools", every vendor name from the registry inside `table.cmp`, every category title, the text "falls short" with "participatory budgeting" and "SSO" nearby, `id="sources"`, links to `/alternatives/maptionnaire/`, `/alternatives/social-pinpoint/` and `/alternatives/metroquest/`, `id="pricing"` with "$49" and "$490", `id="related"`, a FAQPage JSON-LD block, and at least 1,500 visible words

#### Scenario: Registry drives sitemap, robots and hreflang
- **WHEN** `/sitemap.xml`, `/robots.txt` and the page are fetched
- **THEN** the sitemap lists `/participatory-mapping-tools/` with `<lastmod>2026-10-06</lastmod>`, robots carries `Allow: /participatory-mapping-tools/`, and the page's `x-default` hreflang equals its canonical

### Requirement: Mapsurvey is one row with its gaps stated
The comparison table SHALL list Mapsurvey as one row among the vendors, in the same column set, and the page SHALL state Mapsurvey's gaps in prose: no participatory budgeting, no discussion between respondents, no SSO, no formal accessibility audit, hosted in the United States with self-hosting as the residency route. The page SHALL NOT claim EU hosting.

#### Scenario: Gaps are on the page
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** the page contains "participatory budgeting", "SSO" and "United States" inside the gaps block and does not contain "EU-hosted" or "Frankfurt"

### Requirement: Sources and verified dates are rendered
Every vendor in the table SHALL have a "Verified" cell showing the earliest verified date among its facts, and the sources list SHALL show, per vendor, every distinct source URL as a link with its verified date.

#### Scenario: Sources list is complete
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** for every vendor in the registry, every distinct fact source URL appears as an `href` inside `id="sources"`, and the vendor's earliest verified date appears in its table row

### Requirement: Links up and down
Every `/alternatives/` page SHALL link to `/participatory-mapping-tools/` in its breadcrumb JSON-LD and in its body; the landing footer and the sibling partial SHALL link to it; `/alternatives/` SHALL redirect permanently to it.

#### Scenario: Alternatives pages link up
- **WHEN** `/alternatives/maptionnaire/` is rendered
- **THEN** its BreadcrumbList JSON-LD lists `Home`, `Participatory mapping tools`, `Maptionnaire Alternative` and its body contains `href="/participatory-mapping-tools/"`

#### Scenario: Old breadcrumb parent resolves
- **WHEN** `/alternatives/` is requested
- **THEN** the response is a 301 to `/participatory-mapping-tools/`

#### Scenario: Category pages link down
- **WHEN** `/community-engagement-platform/` is rendered
- **THEN** the block under `id="related"` links to `/participatory-mapping-tools/`
