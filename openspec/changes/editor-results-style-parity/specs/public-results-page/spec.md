## ADDED Requirements

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
- **THEN** each option's label includes that question's type and current response count (e.g. "Rate us — Choices · 12 responses")

## MODIFIED Requirements

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
