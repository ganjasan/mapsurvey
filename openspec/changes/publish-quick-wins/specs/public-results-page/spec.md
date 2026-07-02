## ADDED Requirements

### Requirement: Block creation lands in the new block's configuration
After adding a block, the editor SHALL be redirected to that block's configuration view (`?block=<id>`), not the page-settings view, so the just-created block can be configured immediately (the live preview scrolls to it).

#### Scenario: Add block redirect
- **WHEN** the editor submits the Add block form
- **THEN** the response redirects to the Publish space with the new block selected

### Requirement: Live vocabulary and honest state labels
The page's publication state SHALL be described with one term — **live**: the settings toggle reads "Page is live"; the publishing widget shows "Live — /r/<slug>/" when published and "Draft — not live yet" when a page exists but is unpublished, reserving "Set up a results page…" for surveys with no page at all. The address field SHALL be labeled "Page address" (storage and Apply mechanics unchanged).

#### Scenario: Widget distinguishes draft page from no page
- **WHEN** a results page exists with `is_published=False`
- **THEN** the publishing widget shows "Draft — not live yet" with a link into the Publish space

### Requirement: Human-readable visualization names and masking note honesty
Visualization selects SHALL show human labels (e.g. "Markers", "Heatmap", "Bar chart", "Pie", "Donut", "Table") while storing the existing values. The "Small groups are masked to protect privacy." note SHALL render only when `k_anonymity_threshold > 1`.

#### Scenario: Masking note hidden when masking disabled
- **WHEN** a page has `k_anonymity_threshold = 1`
- **THEN** chart blocks render without the masking note

#### Scenario: Masking note shown when masking active
- **WHEN** a page has `k_anonymity_threshold >= 2`
- **THEN** chart blocks include the masking note
