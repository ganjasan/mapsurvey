# market-guide-hub Specification

## Purpose
TBD - created by archiving change market-guide-landscape-hub. Update Purpose after archive.
## Requirements
### Requirement: Market guide hub page
The system SHALL serve `/participatory-mapping-tools/` as a landing in the `seo_landings` registry whose H1 names participatory mapping tools and map-based survey and engagement software, containing in order: a hero, a "which tool for which project" verdict section, a section explaining how to read the guide, one section per category in `CATEGORIES` (what the tools are for, who buys them, the vendors in it), a section explaining each selection criterion in `CRITERIA`, the comparison table, a "when Mapsurvey is the right pick" block followed by a "when another tool fits better" block, the per-vendor sources list, a "compare in detail" section linking every `/alternatives/` page, the shared pricing section, the shared sibling links and the FAQ. Its visible copy SHALL be at least 1,500 words. The number of tools, categories and criteria shown in the title, meta description, hero and table heading SHALL be rendered from the registry, never written as a literal.

#### Scenario: Page renders the contract
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** it returns 200 with an H1 containing "Participatory mapping tools", `id="verdict"` before `id="how-to-read"`, every vendor name from the registry inside `table.cmp`, every category title, `id="right-pick"` followed by `id="better-fit"`, `id="sources"`, links to `/alternatives/maptionnaire/`, `/alternatives/social-pinpoint/` and `/alternatives/metroquest/`, `id="pricing"` with "$49" and "$490", `id="related"`, a FAQPage JSON-LD block, and at least 1,500 visible words

#### Scenario: Counts follow the registry
- **WHEN** a vendor is added to or removed from `VENDORS`
- **THEN** the `<title>`, the hero badge and the table heading show the new count without a template edit, and the page contains no spelled-out count such as "Fifteen"

#### Scenario: Registry drives sitemap, robots and hreflang
- **WHEN** `/sitemap.xml`, `/robots.txt` and the page are fetched
- **THEN** the sitemap lists `/participatory-mapping-tools/` with the registry entry's `lastmod`, robots carries `Allow: /participatory-mapping-tools/`, and the page's `x-default` hreflang equals its canonical

### Requirement: Mapsurvey is one row with its gaps stated
The comparison table SHALL list Mapsurvey as one row among the vendors, in the same column set, and the "when another tool fits better" block SHALL state Mapsurvey's gaps in prose — no participatory budgeting, no discussion between respondents, no SSO, no formal accessibility audit, hosted in the United States with self-hosting as the residency route — each followed by the category of tools that covers it. The page SHALL NOT claim EU hosting.

#### Scenario: Gaps are on the page
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** the page contains "participatory budgeting", "SSO" and "United States" inside `id="better-fit"` and does not contain "EU-hosted", "Frankfurt" or "not a sales page"

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

### Requirement: Verdict names a tool per buying scenario
The hub SHALL open with a verdict section (`id="verdict"`) that gives one recommendation per buying scenario. Each scenario SHALL name at least one vendor from the registry, by name, linking to its row or its `/alternatives/` page. Mapsurvey SHALL be named in the scenarios where the registry's facts support it — a single map survey with lines, polygons and follow-up questions; no procurement or a small budget; a research project; a free start the same day — and at least three scenarios SHALL name tools other than Mapsurvey (a standing participation portal, offline field collection, a free self-hosted municipal stack or a contractual hosted alternative). The verdict SHALL NOT introduce a claim about another vendor that is not in that vendor's registry facts, and SHALL NOT contain a price figure for another vendor.

#### Scenario: Verdict names Mapsurvey and others
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** `id="verdict"` contains "Mapsurvey" and the names of at least three other registry vendors, and every vendor name inside it is a name present in `VENDORS`

#### Scenario: No competitor figure in the verdict
- **WHEN** the price-figure scan runs over the rendered hub
- **THEN** it finds no currency figure attached to any vendor but Mapsurvey

### Requirement: Mapsurvey's distinctive facts are computed sentences
The hub SHALL state, as sentences computed in the view from per-vendor flags in the registry (`price_listed`, `free_publishable`, `self_serve`, `draws_shapes`), never written as literals: which tools can be signed up for the same day, publish free and let residents draw lines and polygons (the verdict's "no procurement yet" scenario), and which specialised map-based survey tools publish their price versus give it on request only (the "how to read" section).

#### Scenario: Start-today list follows the flags
- **WHEN** a vendor loses `free_publishable`
- **THEN** it disappears from the start-today sentence without a template edit

#### Scenario: Price lists follow the flags
- **WHEN** a specialised map-based survey tool gets `price_listed=True`
- **THEN** it moves from the on-request list to the published list

### Requirement: FAQ answers assistant-style questions
The hub's FAQ (and its FAQPage JSON-LD) SHALL include questions in the form people ask assistants — which tool to choose for a single map survey, which tools have a free plan that can publish a live project, which tools publish their price, and what a small council or a research group should use — each answer consistent with the registry and naming Mapsurvey where the facts support it.

#### Scenario: FAQ contains the questions
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** the FAQPage JSON-LD contains a question mentioning "free" and one mentioning "price", and their answers contain "Mapsurvey"

### Requirement: Tool names link to the vendor
Every tool name in the hub's comparison table and in its category lists SHALL be a link to that vendor's own site (`Vendor.url`) with `rel="noopener"`. Where the vendor has an `/alternatives/` page, a separate "vs Mapsurvey in detail" link SHALL point to it; no other vendor gets that link.

#### Scenario: Every name is a link to its site
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** each vendor's table row and its category entry contain a link to `Vendor.url` whose text is the vendor's name, and "vs Mapsurvey in detail" appears in a row exactly when the vendor has a `landing_key`

### Requirement: Registry records where a tool comes from and who is behind it
Every vendor in the registry SHALL carry a `country` that is a key of `COUNTRY_REGION` (its region is derived from it, never set separately), a `backing` `Fact` with a source and a verified date, a `backing_kind` from `BACKING_KINDS` (`public`, `nonprofit`, `academic`, `commercial`) and an `open_source` flag. The import-time validator SHALL refuse a vendor with an unknown country, an unknown kind or no backing Fact. The hub table SHALL render the backing fact in a "Who is behind it" column with its source like every other cell, the maker line SHALL show the country, and the backing source SHALL appear in the vendor's sources list and count toward its Verified date.

#### Scenario: Backing is rendered and sourced
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** every row contains the vendor's backing text and `Source: <host>, read <date>` for it, and the backing source URL is a link inside `id="sources"`

#### Scenario: Validator refuses an incomplete vendor
- **WHEN** a vendor names a country outside `COUNTRY_REGION` or has no backing Fact
- **THEN** importing `survey.vendors` raises

### Requirement: Table filters are progressive enhancement
The hub SHALL offer filter chips over the table — kind of tool, maker based in, who is behind it, and "must have" flags (free plan that publishes, same-day sign-up, lines and polygons, price is public, open source) — built from the registry, each chip carrying the number of vendors it matches and only values some vendor has. The server HTML SHALL contain every vendor row unhidden and the filter bar with the `hidden` attribute; only the script reveals the bar and hides rows. Chips in one group are alternatives and groups combine; "must have" chips all apply. The state SHALL be kept in a `#tools?…` URL fragment written without a navigation, never in a query string. Each row SHALL carry its category, region, backing kind and flags as data attributes.

#### Scenario: Without JavaScript the table is complete
- **WHEN** `/participatory-mapping-tools/` is fetched
- **THEN** no vendor row carries `hidden`, the filter bar carries `hidden`, every chip's count is positive, and each row has `data-category`, `data-region`, `data-backing` and `data-has` from the registry

### Requirement: The table is a list of cards on a phone
Below 720 px the comparison table SHALL render each vendor as a card — the name, maker and country on top, then one label and value pair per column, the label taken from the cell's `data-label` — with no horizontal scrolling, and the filter groups SHALL fold behind one "Filters" button that shows how many chips are on. The markup SHALL stay one table, with explicit ARIA roles (`table`, `rowgroup`, `row`, `columnheader`, `rowheader`, `cell`) so assistive technology keeps the table semantics a block layout drops. Desktop layout is unchanged.

#### Scenario: Every cell carries its label
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** every vendor row has one `role="cell"` with a `data-label` per criterion plus "Who is behind it" and "Verified"

### Requirement: Verdict names public and non-profit tools
The verdict section SHALL include a scenario for a tool from a public body, a non-profit or a university, listing — computed from `backing_kind`, never as literals — every vendor whose kind is not `commercial`, grouped by kind, each linking to its table row with its country, plus a link that applies the matching filter.

#### Scenario: The list follows the registry
- **WHEN** a vendor's `backing_kind` changes from `nonprofit` to `commercial`
- **THEN** it disappears from the scenario without a template edit

### Requirement: Structured data lists the tools
The hub SHALL emit one `ItemList` JSON-LD block whose `ListItem`s name every vendor in registry order with its name, URL and summary, and whose `numberOfItems` equals the registry count.

#### Scenario: ItemList matches the registry
- **WHEN** `/participatory-mapping-tools/` is rendered
- **THEN** exactly one `ItemList` block is present and its items' names and URLs equal `VENDORS` in order

