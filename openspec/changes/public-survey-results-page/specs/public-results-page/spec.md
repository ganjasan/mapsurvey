## ADDED Requirements

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
The system SHALL expose configuration of the public results page only to users with editor rights on the survey, under `/editor/surveys/<uuid>/public-results/`. The public page view itself SHALL be read-only and require no authentication.

#### Scenario: Editor can configure
- **WHEN** a user with editor rights opens the public-results configuration tab
- **THEN** the system renders the configuration UI for that survey's results page

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
The creator SHALL compose the page from an ordered list of blocks. Each block is one of: `text`, `counter`, `chart` (bound to a question), or `map` (bound to a geo question). Blocks SHALL render in the creator-defined order, and the order SHALL be editable via drag-and-drop. A block may be individually hidden without deletion. A `chart` block SHALL render using the creator-selected visualization (`auto`/`bar` as a bar chart, `pie`, `donut`, or `table`); a `map` block SHALL render using its selected visualization (`auto` markers or `heatmap`).

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
Map blocks SHALL render geometry (points/lines/polygons) and optional heatmaps without exposing respondent identity. A geo feature popup SHALL show only the label fields explicitly selected by the creator, defaulting to none. The page SHALL never expose record-level identifiers such as session id, IP, UTM parameters, or per-record timestamps.

#### Scenario: Default popup is empty of attributes
- **WHEN** a creator adds a map block without selecting any popup label fields
- **THEN** geo feature popups display geometry only, with no attribute values

#### Scenario: Only selected fields appear in popups
- **WHEN** a creator selects "issue type" as the only popup field
- **THEN** popups show the issue type value and no other answer fields

#### Scenario: No record identifiers in geo payload
- **WHEN** a visitor inspects the geo data served to the public page
- **THEN** it contains no session id, IP, UTM, or per-record timestamp fields

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
