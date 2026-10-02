# analytics-data-workspace Specification

## Purpose
TBD - created by archiving change fix-analytics-map-collapse. Update Purpose after archive.
## Requirements
### Requirement: Data workspace keeps its height through tab switches
The Responses workspace SHALL retain its flex-column layout (and therefore the full height of its
pane containers, including any split-pane tree) after any number of pane switches through the flat
pane set (Overview/Map/Responses/Charts/Performance) and after the mobile bottom bar selects any
pane. The Map pane's Leaflet container SHALL have a non-zero height whenever the Map pane is
shown, on every form factor, including after entering and leaving split view.

#### Scenario: Map pane on mobile at page load
- **WHEN** the analytics page loads below 768px and the user selects the Map pane
- **THEN** the map container has non-zero height and renders tiles and features

#### Scenario: Desktop pane round-trip
- **WHEN** the user switches Map → Performance → Map through the pane row
- **THEN** the map container keeps a non-zero height and stays rendered

#### Scenario: Split view round-trip
- **WHEN** the user enables split view with the Map pane visible, then closes the split
- **THEN** the map container keeps a non-zero height and `invalidateSize` restores full-width tiles

### Requirement: Fullscreen toggles degrade gracefully
Panel fullscreen controls SHALL use the unprefixed Fullscreen API when present,
fall back to the webkit-prefixed API, and do nothing (without throwing) when
neither exists.

#### Scenario: Expand button on iOS Safari
- **WHEN** the user taps a fullscreen toggle in a browser without
  `Element.requestFullscreen`
- **THEN** no exception is thrown

### Requirement: Global filter pills row
Active FilterManager filters SHALL render as a pills row visible above the workspace on every
pane and form factor. Each pill SHALL name its source value and remove its filter when dismissed;
a "clear all" affordance SHALL remove every filter. The row SHALL show the filtered-vs-total
count (e.g. "20 of 65 shown") and SHALL NOT occupy space when no filter is active.

#### Scenario: Filter set on Charts follows to Map
- **WHEN** the creator clicks a chart segment to filter and switches to the Map pane
- **THEN** the same pill row with the same filter and count renders above the map

#### Scenario: Dismissing the pill restores the data
- **WHEN** the creator dismisses the only active pill
- **THEN** all panes show the full dataset and the pills row disappears

### Requirement: Cross-filtering is discoverable
Chart segments SHALL present an interactive cursor and a visible hint (per chart or one-time)
that clicking filters the workspace. Map selection tools (select/box/lasso) SHALL be labeled
controls, not icon-only buttons.

#### Scenario: First-time hint on charts
- **WHEN** a creator views a question chart before ever applying a chart filter
- **THEN** a "click a bar to filter" hint is visible on or near the chart

### Requirement: Response table defaults serve reading, not administration
When `RESPONSES_V2` is on the response table SHALL default to: per-survey sequence number, start
time, duration, status chip, then answer columns; language and version columns SHALL be available
but hidden by default. Validation status SHALL render as a chip opening a control on demand, not
as an always-rendered per-row select. The Violations sidebar SHALL be replaced by toolbar filter
chips (all / complete / issues / trash) with counts. Trash SHALL be a view chip, not an
action-styled button. Row activation SHALL open the session detail surface.

#### Scenario: Default columns fit reading order
- **WHEN** the Responses pane renders with default settings
- **THEN** sequence, start time, duration and status precede answer columns, and language/version
  are hidden until enabled via the columns control

#### Scenario: Issues chip filters like the old sidebar
- **WHEN** the creator activates the "issues" chip
- **THEN** the table shows only sessions with violations and the chip shows their count

### Requirement: Violation filtering keeps per-type selection
The Issues control SHALL open a menu listing every violation type present in the
data, grouped into errors and warnings, each with its own count, and SHALL allow
any combination of types to be selected at once (a session matching any selected
type is shown). The control SHALL report how many types are selected and offer a
one-action clear. Replacing the Violations sidebar with a single all-or-nothing
chip is not sufficient. The `empty` type SHALL NOT be offered in the menu: empty
sessions are shown or hidden by the control described in `responses-empty-sessions`,
and when shown they keep their "Empty" badge.

#### Scenario: Selecting one violation type
- **WHEN** the creator opens the Issues menu and ticks "Duplicate"
- **THEN** only duplicate sessions are listed and the control reads "1 selected"

#### Scenario: Selecting several types at once
- **WHEN** the creator additionally ticks "Incomplete"
- **THEN** sessions flagged duplicate **or** incomplete are listed and the control
  reads "2 selected"

#### Scenario: Types with no occurrences are not offered
- **WHEN** a violation type has a zero count for the current survey
- **THEN** the menu omits it rather than offering an empty filter

#### Scenario: Empty is not an Issues entry
- **WHEN** the creator shows empty sessions and opens the Issues menu
- **THEN** the menu has no "Empty sessions" entry, and the empty rows in the table carry the
  "Empty" badge

### Requirement: Free-text search across the response table
The Responses toolbar SHALL provide a search field that filters rows by matching
the query against every column of a row — sequence number, start time, status,
violations, tags, notes and all answer values — case-insensitively. Searching
SHALL compose with the chip, violation and per-column filters, and SHALL NOT
alter the chip counts, which describe the unsearched set. Per-column sorting and
per-column filtering SHALL remain available on every column header.

#### Scenario: Query narrows the table
- **WHEN** the creator types a word occurring in one answer
- **THEN** only rows containing it anywhere survive and the toolbar reports the
  reduced count

#### Scenario: Search keeps the caret
- **WHEN** the creator keeps typing while the table reloads
- **THEN** focus and caret stay in the search field and no keystroke is lost

#### Scenario: Sorting and column filters still available
- **WHEN** the creator uses a column header's sort or filter control
- **THEN** the table sorts or filters by that column as before the refactor

### Requirement: Split view is an explicit labeled mode
Split view SHALL be entered from a labeled control in the pane row (desktop only). Panes inside a
split SHALL NOT render their own pane tab bars; the pane row governs pane placement. The split
layout SHALL persist per survey and a visible reset SHALL restore the single-pane layout.

#### Scenario: Entering split view
- **WHEN** the creator activates "Split view" on desktop
- **THEN** a second pane opens beside the current one and both active panes are indicated in the
  pane row

#### Scenario: Reset layout
- **WHEN** the creator activates the split view reset
- **THEN** the workspace returns to a single full-width pane and the persisted layout is cleared

### Requirement: Responses maps share one mount lifecycle
Every Leaflet map on the Responses page SHALL be created through one shared helper
(`EditorMap.mount`), never by a direct `L.map(...)` call in a template — the Map pane, the Overview
thumbnail, the response detail mini-map and the full-size response modal alike. The helper SHALL keep
the map instance on its container element, never in a page global; SHALL dispose any map already
mounted on that element, or whose element has left the document, before creating a new one; SHALL
never raise while disposing; and SHALL run a surface's layer-adding and fitting code only once the
container has a non-zero size.

Rationale: the drawer mini-map is re-created on every HTMX swap. Holding the previous instance in a
global and calling `remove()` on it after its DOM was discarded threw once, left Leaflet's
container id half-cleared, and then threw "Map container is being reused by another instance" on
every later open in that session. Drawing before layout threw on the first polygon. One helper
answers all three questions once.

#### Scenario: A second response replaces the first mini-map without error
- **WHEN** a creator opens one response's detail and then another
- **THEN** the first mini-map is disposed without raising and the second mounts and draws its features

#### Scenario: A map mounted into a hidden container draws when it becomes visible
- **WHEN** a surface mounts a map while its container is 0×0 (an overlay drawer before layout, a hidden pane)
- **THEN** no layer is added and nothing is fitted until the container has a size, after which the surface's features are drawn once

#### Scenario: A half-torn map cannot poison its container
- **WHEN** Leaflet's own `remove()` throws part-way through disposing a map
- **THEN** the container is still left mountable — its Leaflet id and panes cleared — and the next mount on it succeeds

#### Scenario: A swapped-away element takes its map with it
- **WHEN** HTMX discards the element a map is mounted on
- **THEN** the map is disposed with the element and no reference to it survives the swap

#### Scenario: A direct Leaflet mount in an analytics template fails the build
- **WHEN** an analytics template calls `L.map(` instead of the helper
- **THEN** the source guard fails, naming the template

### Requirement: Inline answer editing is limited to single-value types

The inline answer edit endpoint SHALL accept only question types in the shared editable list
(`text`, `text_line`, `number`, `range`, `choice`, `multichoice`, `rating`, `datetime`) and SHALL
reject any other type with HTTP 400 without reading or writing answers. For an editable type it
SHALL update the earliest existing root answer of that session and question, or create one when
none exists, and SHALL NOT fail when more than one root answer exists. The Responses table SHALL
offer inline editing only on columns of an editable type.

#### Scenario: Editing a multi-feature geo answer is refused, not crashed

- **GIVEN** a session with three root answers to a `point` question
- **WHEN** an editor POSTs a new value for that session and question
- **THEN** the response is 400 and the three answers are unchanged

#### Scenario: Editing an unanswered geo question creates nothing

- **GIVEN** a session with no answer to a `polygon` question
- **WHEN** an editor POSTs a value for it
- **THEN** the response is 400 and no answer row is created

#### Scenario: Editing a text answer still works and tolerates duplicates

- **GIVEN** a session with two root answers to a `text` question
- **WHEN** an editor POSTs `"new"` for it
- **THEN** the response is 204 and the earliest answer's text is `"new"`

#### Scenario: Geo columns are not editable in the table

- **WHEN** the Responses table renders a `point` column and a `text` column for an editor
- **THEN** only the text cells carry the double-click edit handler

