# public-results-page Specification

## Purpose
TBD - created by archiving change publish-quick-wins. Update Purpose after archive.
## Requirements
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

### Requirement: Public results page existence and addressing
The system SHALL provide a per-survey public results page, bound 1:1 to a `SurveyHeader`, served at `/r/<slug>/` where `slug` is unique and independent of the survey slug. The page SHALL be reachable only when it is published.

#### Scenario: Published page is reachable
- **WHEN** an anonymous visitor opens `/r/<slug>/` for a published results page
- **THEN** the system returns 200 and renders the page

#### Scenario: Unpublished page is not reachable
- **WHEN** an anonymous visitor opens `/r/<slug>/` for a results page that is not published
- **THEN** the system returns 404

#### Scenario: Unknown slug
- **WHEN** an anonymous visitor opens `/r/<slug>/` for a slug that does not exist
- **THEN** the system returns 404

#### Scenario: Slug is independent of survey slug
- **WHEN** a creator sets the results-page slug to a value different from the survey slug
- **THEN** the page is served at `/r/<that-slug>/` and the survey's own public URL is unaffected

### Requirement: Creator-only configuration
The system SHALL expose configuration of the public results page only to users with editor rights on the survey, under `/editor/surveys/<uuid>/public-results/`. The public page view itself SHALL be read-only and require no authentication. Configuration changes SHALL save automatically on edit, without an explicit Save action; the slug (which is the public address) is the sole exception and SHALL be applied via an explicit control. The sidebar SHALL share its visual styling with the Survey Editor's sidebar (see "Editor sidebar visual consistency with the Survey Editor").

#### Scenario: Editor can configure
- **WHEN** a user with editor rights opens the public-results configuration tab
- **THEN** the system renders the configuration UI for that survey's results page, styled consistently with the Survey Editor sidebar

#### Scenario: Configuration autosaves
- **WHEN** an editor changes any page or block setting other than the slug
- **THEN** the change is persisted automatically (no Save button) and the editor preview reflects it
- **AND** the slug is applied only via its explicit Apply control, so the public URL never changes from a half-typed value
- **AND** without JavaScript, the explicit Save buttons remain available (graceful degradation)

#### Scenario: Non-editor cannot configure
- **WHEN** a user without editor rights requests the public-results configuration endpoint
- **THEN** the system denies access (403/redirect per existing permission behavior)

#### Scenario: Public view performs no writes
- **WHEN** an anonymous visitor loads the published public results page
- **THEN** the system serves it read-only and does not create or mutate any survey, session, or answer records

### Requirement: Visibility control
The page SHALL support two visibility modes: `public` and `unlisted`. Public pages SHALL be indexable (`robots: index`) and eligible for the public stories listing and sitemap. Unlisted pages SHALL emit `robots: noindex`, SHALL be excluded from the stories listing and sitemap, and SHALL remain reachable by direct link.

#### Scenario: Public page is indexable
- **WHEN** a published page has visibility `public`
- **THEN** its HTML contains a `robots` meta allowing indexing and it is eligible to appear in the stories listing

#### Scenario: Unlisted page is not indexed
- **WHEN** a published page has visibility `unlisted`
- **THEN** its HTML contains `robots: noindex` and it does not appear in the stories listing or sitemap

#### Scenario: Unlisted page still opens by direct link
- **WHEN** an anonymous visitor opens the direct `/r/<slug>/` URL of an unlisted published page
- **THEN** the system returns 200 and renders the page

### Requirement: Curated content blocks
The creator SHALL compose the page from an ordered list of blocks. Each block is one of: `text`, `image`, `chart` (bound to a question), or `map` (bound to a geo question) — there is no standalone counter block, since the response count is already available as a page-level affordance (see "Engagement affordances and platform footer"). Blocks SHALL render in the creator-defined order, and the order SHALL be editable via drag-and-drop. A block may be individually hidden without deletion. A `chart` block SHALL render using the creator-selected visualization (`auto`/`bar` as a bar chart, `pie`, `donut`, or `table`); a `map` block SHALL render using its selected visualization (`auto` markers or `heatmap`) over a creator-selected basemap (`streets`/`satellite`/`topo`, default `streets`). In `heatmap` mode the individual point markers SHALL NOT be drawn (they would obscure the heat layer); non-point geometries still render as shapes. An `image` block holds one creator-uploaded image with an optional multilingual caption; a block with no image attached (defensive) is omitted from rendering, mirroring a chart/map block whose question was deleted.

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
- **WHEN** the creator selects a basemap (`streets`, `satellite`, or `topo`) for a map block
- **THEN** the map renders over that tile layer; the payload carries the selected basemap (default `streets`)

#### Scenario: Image block renders with caption
- **WHEN** the creator adds an image block with an uploaded file and a caption
- **THEN** the public page renders the image and the caption text

#### Scenario: Image block without a file is omitted
- **WHEN** an image block somehow has no file attached
- **THEN** it produces no payload and is not rendered

### Requirement: Text answers are never published
The block-creation picker SHALL NOT allow adding `text` / `text_line` questions as result blocks, and the public page SHALL never display individual free-text answers.

#### Scenario: Text question is not offered as a block
- **WHEN** the creator opens the "Add block" question picker
- **THEN** text and text_line questions are shown as unavailable and cannot be added

#### Scenario: No raw texts on the public page
- **WHEN** a visitor loads any published results page
- **THEN** no individual free-text answer value appears anywhere on the page

### Requirement: Hybrid live / frozen data
The page SHALL support a `live` mode and a `frozen` mode. In live mode, blocks SHALL render current aggregates computed via the existing analytics service, cached for at most 60 seconds. In frozen mode, blocks SHALL render from a stored snapshot and SHALL NOT change when new responses arrive. The creator SHALL be able to freeze, refresh the snapshot, and return to live.

#### Scenario: Live reflects new responses
- **WHEN** the page is in live mode and a new valid response arrives, after the cache window elapses
- **THEN** the rendered aggregates and response count reflect the new response

#### Scenario: Frozen does not change
- **WHEN** the page is in frozen mode and a new valid response arrives
- **THEN** the rendered aggregates and response count remain equal to the snapshot taken at freeze time

#### Scenario: Freeze captures current data
- **WHEN** the creator freezes the page
- **THEN** the system stores a snapshot of the current per-block payloads and records the freeze timestamp

#### Scenario: Return to live
- **WHEN** the creator switches a frozen page back to live
- **THEN** subsequent renders compute aggregates from current data again

#### Scenario: Configuration change is reflected immediately
- **WHEN** the page is in live mode and the creator adds, edits, deletes, or reorders a block
- **THEN** the editor preview and the public page reflect the change on the next render, without waiting for the live-cache window to elapse
- **AND** the 60-second cache window still applies to newly arriving responses (data), not to configuration changes

### Requirement: Clean-session data source on the canonical survey
Aggregates and geo features SHALL be computed only from sessions that are not deleted and not marked invalid, aggregated against the canonical survey, reusing the existing analytics filtering.

#### Scenario: Deleted and invalid sessions excluded
- **WHEN** a survey has sessions that are deleted or marked invalid
- **THEN** those sessions contribute to neither the counts, charts, nor map of the public page

#### Scenario: Aggregation spans versions via canonical survey
- **WHEN** a survey has multiple published versions sharing one canonical survey
- **THEN** the public page aggregates responses across versions and the response count does not reset on a version transition

### Requirement: Anonymous geo display
The public page SHALL render geo answers (points/lines/polygons) as anonymous geometry. Each geometry's popup SHALL expose only per-point attributes that the creator explicitly selected — namely the **sub-questions of that geo question** — resolved from that geometry's own sub-answers (`parent_answer`). Popups SHALL NOT be filled from session-level answers, SHALL NOT include free-text answers, and SHALL NEVER expose record identifiers (session id, IP, UTM, timestamps). A geo question with no eligible (non-text) sub-questions SHALL render anonymous geometry only.

#### Scenario: Default popup is empty of attributes
- **WHEN** a map block has no popup fields selected
- **THEN** each feature's properties are empty and no identifiers appear anywhere in the payload

#### Scenario: Popup shows only selected sub-question attributes, per point
- **WHEN** a map block selects one sub-question of its geo question as a popup field
- **THEN** each point's popup shows that point's own answer to the sub-question, and points from the same respondent can show different values

#### Scenario: Free-text sub-answers are never shown
- **WHEN** a geo question has a free-text sub-question
- **THEN** it is not offered as a popup field and never appears in any point's popup

#### Scenario: Editor offers the geo question's sub-questions as popup fields
- **WHEN** the creator configures a map block whose geo question has sub-questions
- **THEN** the "Geo popup fields" picker lists those sub-questions (not unrelated top-level questions)

### Requirement: k-anonymity masking of small buckets
The page SHALL apply a per-page k-anonymity threshold (default 3). Any aggregate bucket whose count is greater than zero but less than the threshold SHALL be displayed as "<K" instead of its exact count. A threshold of 1 SHALL disable masking.

#### Scenario: Small bucket is masked
- **WHEN** a choice option has been selected by 2 respondents and the threshold is 3
- **THEN** that option's count is displayed as "<3" rather than "2"

#### Scenario: Large bucket is exact
- **WHEN** a choice option has been selected by 40 respondents and the threshold is 3
- **THEN** that option's count is displayed as "40"

#### Scenario: Masking disabled at threshold 1
- **WHEN** the threshold is set to 1
- **THEN** all bucket counts are displayed exactly with no masking

### Requirement: Engagement affordances and platform footer
The page SHALL optionally display a response counter and a "Take the survey" CTA. The CTA SHALL appear only while the underlying survey is open to responses and SHALL be hidden otherwise. Every public results page SHALL display a "Made with Mapsurvey" footer linking to the platform.

#### Scenario: Counter shown when enabled
- **WHEN** the response counter is enabled
- **THEN** the page displays the total count of clean responses

#### Scenario: CTA visible while survey is open
- **WHEN** the CTA is enabled and the survey is open to responses
- **THEN** the page shows a "Take the survey" action linking to the survey

#### Scenario: CTA hidden when survey is closed
- **WHEN** the CTA is enabled but the survey is closed to responses
- **THEN** the page does not show the "Take the survey" action

#### Scenario: Platform footer always present
- **WHEN** any published public results page is rendered
- **THEN** it includes a "Made with Mapsurvey" footer linking to the platform

### Requirement: Graceful handling of empty and broken state
The page SHALL render without error when there is no data or when a referenced question is missing. A page with zero responses SHALL show the intro and an empty-state message instead of empty charts. A block referencing a deleted question SHALL be silently omitted.

#### Scenario: Zero responses
- **WHEN** a published page has no clean responses
- **THEN** the page renders the intro and an empty-state message and does not render empty charts

#### Scenario: Deleted question in a block
- **WHEN** a block references a question that has been deleted from the survey
- **THEN** that block is silently omitted and the rest of the page renders normally

#### Scenario: Draft survey cannot publish results
- **WHEN** the underlying survey is in draft status
- **THEN** the system does not allow publishing its results page

### Requirement: Editor sidebar visual consistency with the Survey Editor
The Public Results configuration sidebar SHALL reuse the Survey Editor's shared sidebar CSS (`.editor-sidebar`, `.sidebar-header`, `.section-list`/`.section-item`, `.sidebar-footer`, `.add-question-btn`, `.sidebar-pinned`/`.sidebar-pinned-item`) for the "Page settings" pinned entry, the "Content blocks" header, and the block list, instead of parallel bespoke styling. Adding a block SHALL be triggered by a single dashed "+ Add block" button (same style as "+ New Question"/"+ New Section") that opens a modal containing the block-type choice (labeled "Question results…", "Image", "Text block" — not the ambiguous bare "Question…") and, for question-bound blocks, a question picker whose options each display that question's type and current response count — rather than an always-visible inline select/button row.

#### Scenario: Blocks list matches the section list styling
- **WHEN** an editor opens the Public Results configuration tab
- **THEN** the "Content blocks" header and each block row render with the same padding, hover, active, and drag-handle styling as the Survey Editor's section list

#### Scenario: Adding a block opens a modal
- **WHEN** the editor clicks "+ Add block"
- **THEN** a modal opens with the block-type selection (and the question picker when "Question results…" is chosen, with text questions disabled as before); submitting it behaves exactly as the existing add-block endpoint did (redirect on success, 400 on an unpublishable question)

#### Scenario: Question picker shows type and response count
- **WHEN** the editor opens the question picker after choosing "Question results…"
- **THEN** each option shows the question name and, on a visually distinct second line, its type and current response count (e.g. name "Rate us" with a muted "Choices · 12 responses" beneath it)

#### Scenario: Question picker is searchable by name and type
- **WHEN** the editor types into the picker's search box
- **THEN** the option list filters to questions whose name OR type contains the query (case-insensitive), and shows an empty-state message when nothing matches

#### Scenario: Long question text wraps instead of overflowing
- **WHEN** the question picker is opened and an option's label is too long to fit on one line
- **THEN** the label wraps onto multiple lines within the picker's width instead of being clipped or overflowing the modal (a native `<select>` popup cannot wrap option text, so the picker is a custom listbox backed by a hidden `<select>` for form submission)

#### Scenario: Selecting a block scrolls the live preview to it
- **WHEN** the editor selects a content block in the sidebar
- **THEN** the live-preview pane scrolls that block into view and briefly highlights it

