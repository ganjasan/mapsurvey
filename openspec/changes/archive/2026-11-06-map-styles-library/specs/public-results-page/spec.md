## MODIFIED Requirements

### Requirement: Curated content blocks
The creator SHALL compose the page from an ordered list of blocks. Each block is one of: `text`, `image`, `chart` (bound to a question), or `map` (bound to a geo question) — there is no standalone counter block, since the response count is already available as a page-level affordance (see "Engagement affordances and platform footer"). Blocks SHALL render in the creator-defined order, and the order SHALL be editable via drag-and-drop. A block may be individually hidden without deletion. A `chart` block SHALL render using the creator-selected visualization (`auto`/`bar` as a bar chart, `pie`, `donut`, or `table`); a `map` block SHALL render using its selected visualization (`auto` markers or `heatmap`) over a creator-selected basemap — any key the map style library resolves for the survey's workspace: a preset or `style:<uuid>` of a workspace style, default `streets`. In `heatmap` mode the individual point markers SHALL NOT be drawn (they would obscure the heat layer); non-point geometries still render as shapes. An `image` block holds one creator-uploaded image with an optional multilingual caption; a block with no image attached (defensive) is omitted from rendering, mirroring a chart/map block whose question was deleted.

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

#### Scenario: Map heatmap shows the heat layer, not markers
- **WHEN** the creator sets a map block's visualization to `heatmap`
- **THEN** the public page renders a heat layer over the point answers and does NOT draw the individual point markers on top of it

#### Scenario: Map basemap is honored
- **WHEN** the creator selects a basemap key offered by the block editor (a preset or one of the workspace's ready styles) for a map block
- **THEN** the map renders over that key's tile layer from the resolver's table; the payload carries the selected key (default `streets`); a key the workspace cannot resolve renders as `streets`

#### Scenario: Image block renders with caption
- **WHEN** the creator adds an image block with an uploaded file and a caption
- **THEN** the public page renders the image and the caption text

#### Scenario: Image block without a file is omitted
- **WHEN** an image block has no file attached
- **THEN** it is omitted from the public page
