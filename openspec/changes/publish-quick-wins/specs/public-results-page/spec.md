## ADDED Requirements

### Requirement: Block creation lands in the new block's configuration
After adding a block, the editor SHALL be redirected to that block's configuration view (`?block=<id>`), not the page-settings view, so the just-created block can be configured immediately (the live preview scrolls to it).

#### Scenario: Add block redirect
- **WHEN** the editor submits the Add block form
- **THEN** the response redirects to the Publish space with the new block selected

### Requirement: Explicit publish / unpublish action
Making the results page live SHALL be an explicit, prominent action in the Publish space's Page-settings bar — a "Publish page" button when unpublished (disabled, with a hint, while the survey itself is a draft) and an "Unpublish" button plus a "live at /r/<slug>/" banner when published. Publish state SHALL be owned by a dedicated endpoint; autosaving other page settings SHALL never change it (there is no publish checkbox in the settings form). The address field SHALL be labeled "Page address" (storage and Apply mechanics unchanged).

#### Scenario: Publish then unpublish
- **WHEN** the editor clicks "Publish page"
- **THEN** the page becomes live at `/r/<slug>/` and the bar shows "Unpublish" + a live banner; clicking "Unpublish" takes it down (the public URL 404s)

#### Scenario: Autosave never changes publish state
- **WHEN** a live page's other settings are autosaved (the form has no publish field)
- **THEN** the page stays live

#### Scenario: Draft survey cannot publish its results page
- **WHEN** the survey is a draft and the publish action is invoked
- **THEN** it is refused and the page stays unpublished

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
