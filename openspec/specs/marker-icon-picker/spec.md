# marker-icon-picker Specification

## Purpose
TBD - created by archiving change editor-icon-picker-expansion. Update Purpose after archive.
## Requirements
### Requirement: Icon catalog covers Font Awesome Free and the map icon sets
The editor SHALL offer marker icons from a generated static catalog containing every Font Awesome
Free 5.15 icon in the solid and regular styles, every Maki icon, and every Temaki icon. Brand
(`fab`) icons SHALL NOT be listed. Each catalog entry SHALL carry the exact `icon_class` value it
writes, a human label, one or more product categories, and search terms per supported language
(EN, RU, DE, ES, FR, PT, PL, ID). The catalog SHALL be produced by a checked-in build script from
upstream metadata, and the committed catalog SHALL be what the editor serves.

#### Scenario: Font Awesome icon outside the old hand-picked list is offered
- **WHEN** a creator opens the picker and searches for "bench"
- **THEN** a Font Awesome or map-set icon for a bench is listed, although no such class was in the former inline list

#### Scenario: Map-set icon is offered with its prefixed value
- **WHEN** a creator selects the Maki "bus" icon
- **THEN** the `icon_class` input holds `maki:bus`

#### Scenario: Brand icons are absent
- **WHEN** the catalog is built
- **THEN** it contains no entry whose value starts with `fab `

#### Scenario: Catalog build reports counts
- **WHEN** the build script runs
- **THEN** it prints the number of icons per set and the number of unique terms translated per language, and exits non-zero if any set is empty

### Requirement: Search matches keywords in the creator's language and in English
The picker SHALL match a query against each icon's label, name, English terms, and the terms for
the creator's UI language. Every whitespace-separated token of the query SHALL match for an icon
to be listed. Matching SHALL be case-insensitive and substring-based, so a stem finds inflected
forms.

#### Scenario: English keyword finds an icon whose class name differs
- **WHEN** the query is "playground"
- **THEN** icons whose terms include playground (for example `fas fa-child`, `maki:playground`) are listed

#### Scenario: Translated keyword finds an icon
- **WHEN** the UI language is Russian and the query is "остановк"
- **THEN** the bus-stop icons are listed

#### Scenario: English still works under a non-English UI
- **WHEN** the UI language is German and the query is "bus"
- **THEN** the bus icons are listed

#### Scenario: Multiple tokens narrow the result
- **WHEN** the query is "bus stop"
- **THEN** only icons matching both "bus" and "stop" are listed

### Requirement: Icons can be browsed by category
The picker SHALL show category chips (All, the product categories, Map). Selecting a chip SHALL
restrict the grid to that category and SHALL combine with the current query. With no query and
"All" selected the grid SHALL list the current value first, then the Map set, then Font Awesome
icons in category order. The grid SHALL render at most 240 cells and SHALL tell the creator to
narrow the search when more match.

#### Scenario: Category restricts the grid
- **WHEN** the creator selects the "Transport" chip with an empty query
- **THEN** only icons in the transport category are listed

#### Scenario: Category and query combine
- **WHEN** the "Nature" chip is selected and the query is "tree"
- **THEN** only nature icons matching "tree" are listed

#### Scenario: Overflow is announced
- **WHEN** more than 240 icons match
- **THEN** 240 cells render and a "type to narrow" hint is shown

#### Scenario: Category labels follow the UI language
- **WHEN** the UI language is Russian
- **THEN** the chips are labelled in Russian, and a category with no Russian label falls back to English

### Requirement: Catalog loads lazily and once
The catalog SHALL be fetched from its static URL the first time the picker opens on a page and
SHALL be reused for every later open on that page. A page whose creator never opens the picker
SHALL NOT fetch the catalog. The gzipped catalog SHALL stay under 350 KB, enforced by a test.

#### Scenario: No fetch before first open
- **WHEN** the question modal renders
- **THEN** no request for the catalog is made until the picker button is pressed

#### Scenario: Size ceiling
- **WHEN** the test suite runs
- **THEN** a test fails if the gzipped catalog exceeds 350 KB

### Requirement: Free-text entry keeps working and is validated
The `icon_class` input SHALL still accept a typed value. On save the value SHALL be accepted when
it is empty, matches `^(fas|far|fab|fa) fa-[a-z0-9-]+$`, or is `<set>:<name>` for a set and name
present in the catalog. Any other value SHALL be rejected with a field error naming the accepted
forms.

#### Scenario: Pasted Font Awesome class saves
- **WHEN** a creator types `fas fa-anchor` and saves
- **THEN** the question stores `fas fa-anchor`

#### Scenario: Unknown map-set name is rejected
- **WHEN** a creator types `maki:benchh` and saves
- **THEN** the form returns a validation error on `icon_class` and nothing is stored

#### Scenario: Legacy v4 class still saves
- **WHEN** an existing question holds `fa fa-bus` and the creator saves an unrelated change
- **THEN** the save succeeds and the value is unchanged

### Requirement: Picker telemetry
The picker SHALL send a PostHog `icon_search_miss` event with `query`, `lang` and `category`
when a query has yielded zero icons for 700 ms after the last keystroke, at most once per
distinct query per picker open. It SHALL send `icon_picked` with `value`, `set` (`fa`, `maki`,
`temaki`) and `via` (`search`, `browse`, `typed`) when a value is chosen. Both SHALL be no-ops
when PostHog is not loaded.

#### Scenario: Miss is reported once
- **WHEN** a creator types "xyzzy", waits, deletes a letter and retypes it
- **THEN** exactly one `icon_search_miss` event with query "xyzzy" is sent

#### Scenario: Pick reports its route
- **WHEN** a creator searches "bench" and clicks a result
- **THEN** an `icon_picked` event with `via: "search"` and the chosen value is sent

#### Scenario: Analytics absent
- **WHEN** `window.posthog` is undefined
- **THEN** the picker works and sends nothing

