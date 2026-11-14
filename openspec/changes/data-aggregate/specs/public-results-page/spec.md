## MODIFIED Requirements

### Requirement: Anonymous geo display
The public page SHALL render geo answers (points/lines/polygons) as a grid of cells counting
distinct respondents, with cells under K omitted (`public-aggregates`), never as the answers' own
geometry. Each cell's popup SHALL show its number of respondents and, for each sub-question of that
geo question the creator explicitly selected, the distribution of the cell's answers to it: choice
counts masked below K, a mean only when at least K values exist. Popups SHALL NOT be filled from
session-level answers, SHALL NOT include free-text answers, and SHALL NEVER expose record
identifiers (session id, IP, UTM, timestamps).

#### Scenario: Default popup shows only the count
- **WHEN** a map block has no popup fields selected
- **THEN** each cell's properties hold its respondent count only and no identifiers appear anywhere in the payload

#### Scenario: Popup shows the cell's distribution of a selected sub-question
- **WHEN** a map block selects a choice sub-question and a cell holds 4 points answered "Unsafe" and 1 answered "No shade", K = 3
- **THEN** the cell's popup shows "Unsafe" 4 and "No shade" "<3"

#### Scenario: Free-text sub-answers are never shown
- **WHEN** a geo question has a free-text sub-question
- **THEN** it is not offered as a popup field and never appears in any cell's popup

#### Scenario: Editor offers the geo question's sub-questions as popup fields
- **WHEN** the creator configures a map block whose geo question has sub-questions
- **THEN** the "Geo popup fields" picker lists those sub-questions (not unrelated top-level questions)

### Requirement: Human-readable visualization names and masking note honesty
Visualization selects SHALL show human labels (e.g. "Bar chart", "Pie", "Donut", "Table") while storing the existing values. The "Small groups are masked to protect privacy." note SHALL render only when `k_anonymity_threshold > 1`.

#### Scenario: Masking note hidden when masking disabled
- **WHEN** a page has `k_anonymity_threshold = 1`
- **THEN** chart blocks render without the masking note

#### Scenario: Masking note shown when masking active
- **WHEN** a page has `k_anonymity_threshold >= 2`
- **THEN** chart blocks include the masking note

### Requirement: Curated content blocks
The creator SHALL compose the page from an ordered list of blocks. Each block is one of: `text`, `image`, `chart` (bound to a question), or `map` (bound to a geo question) — there is no standalone counter block, since the response count is already available as a page-level affordance (see "Engagement affordances and platform footer"). Blocks SHALL render in the creator-defined order, and the order SHALL be editable via drag-and-drop. A block may be individually hidden without deletion. A `chart` block SHALL render using the creator-selected visualization (`auto`/`bar` as a bar chart, `pie`, `donut`, or `table`); a `map` block SHALL render as a grid of cells counting respondents (see "Anonymous geo display" and `public-aggregates`) over a creator-selected basemap — any key the map style library resolves for the survey's workspace: a preset or `style:<uuid>` of a workspace style, default `streets`. The editor SHALL offer no marker, heatmap or cluster choice for a map block; it SHALL say that the public map shows squares counting respondents, hides squares under K, and that exact points stay in Responses and the export. An `image` block holds one creator-uploaded image with an optional multilingual caption; a block with no image attached (defensive) is omitted from rendering, mirroring a chart/map block whose question was deleted.

#### Scenario: Blocks render in configured order
- **WHEN** a visitor loads a page with blocks ordered [intro text, chart, map]
- **THEN** the blocks appear in that exact order

#### Scenario: Hidden block is not shown
- **WHEN** a block is marked hidden
- **THEN** it is omitted from the public page but retained in the configuration

#### Scenario: Reordering persists
- **WHEN** the creator drags a block to a new position and saves
- **THEN** the new order is persisted and reflected on the public page

#### Scenario: Chart visualization is honored
- **WHEN** the creator sets a chart block's visualization to `pie`, `donut`, or `table`
- **THEN** the public page and the editor preview render that visualization, not a bar chart
- **AND** `bar` and `auto` render as a bar chart (preserving the existing horizontal/vertical orientation per data type)

#### Scenario: Map block offers no point visualizations
- **WHEN** the creator selects a map block in the editor
- **THEN** there is no Markers / Heatmap / Clusters choice, and a note says the public map shows squares counting respondents, with squares under K hidden

#### Scenario: Map basemap is honored
- **WHEN** the creator selects a basemap key offered by the block editor (a preset or one of the workspace's ready styles) for a map block
- **THEN** the map renders over that key's tile layer from the resolver's table; the payload carries the selected key (default `streets`); a key the workspace cannot resolve renders as `streets`

#### Scenario: Image block renders with caption
- **WHEN** the creator adds an image block with an uploaded file and a caption
- **THEN** the public page renders the image and the caption text

#### Scenario: Image block without a file is omitted
- **WHEN** an image block has no file attached
- **THEN** it is omitted from the public page
