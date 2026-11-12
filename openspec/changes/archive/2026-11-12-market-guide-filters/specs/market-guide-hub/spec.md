## ADDED Requirements

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
