## ADDED Requirements

### Requirement: Survey settings accessible from the editor sidebar
The system SHALL show a pinned "Survey settings" entry above the section list in the Survey Editor sidebar, styled identically to the "Page settings" pinned entry in the Public Results config tab (shared `.sidebar-pinned`/`.sidebar-pinned-item` classes). Clicking it SHALL swap the center panel to a settings form (general fields, default map position, collaborators, password/test access) via the same HTMX contextual-swap mechanism used for section selection, without a full page reload, and SHALL mark the pinned entry active while clearing any active section. The general-fields form SHALL autosave on field change (mirroring the Public Results settings autosave: selects/checkboxes save immediately, text fields debounce, an inline status indicator replaces the explicit Save button). Loading `/editor/surveys/<uuid>/?panel=settings` SHALL render the settings panel as the initial center-panel content with the pinned entry pre-selected.

#### Scenario: Open settings from the sidebar
- **WHEN** the user clicks the pinned "Survey settings" entry in the editor sidebar
- **THEN** the center panel swaps to the settings form via HTMX (no full page reload), the pinned entry gets the active style, and no section item is shown as active

#### Scenario: Switching back to a section clears settings active state
- **WHEN** the settings panel is open and the user clicks a section in the sidebar
- **THEN** the center panel swaps to that section's detail, the section item becomes active, and the pinned "Survey settings" entry loses its active style

#### Scenario: Deep link opens settings directly
- **WHEN** the user loads `/editor/surveys/<uuid>/?panel=settings`
- **THEN** the initial center-panel content is the settings form and the pinned entry renders with the active style server-side

#### Scenario: General settings autosave on change
- **WHEN** the settings panel is open and the user changes the visibility select or types in a text field (debounced)
- **THEN** the change is persisted via an XHR POST that returns JSON, and the autosave status indicator reflects saving/saved without a page reload

### Requirement: Standalone settings page remains reachable but is no longer the primary link
The top navigation "Settings" tab SHALL link into the Survey Editor with the settings panel pre-selected (`?panel=settings`) instead of the standalone settings page, and SHALL display a small "moved" indicator. The standalone `/editor/surveys/<uuid>/settings/` URL and view SHALL continue to function exactly as before (same template, same GET/POST behavior) for any existing direct links or bookmarks.

#### Scenario: Nav tab opens the in-editor panel
- **WHEN** the user clicks the "Settings" tab in the top navigation
- **THEN** the browser navigates to the Survey Editor with the settings panel already selected, and the tab shows a "moved" indicator

#### Scenario: Direct link to the old settings URL still works
- **WHEN** a user navigates directly to `/editor/surveys/<uuid>/settings/`
- **THEN** the standalone settings page renders exactly as it did before this change

## MODIFIED Requirements

### Requirement: Survey editor layout
The system SHALL render the survey editor at `/editor/surveys/<uuid>/` as a 3-column layout: a left sidebar with a pinned "Survey settings" entry above a list of sections, a center panel showing either the selected section's details and questions or the settings panel, and a right panel showing a live preview iframe. The editor page SHALL load HTMX and SortableJS from CDN.

#### Scenario: Editor page loads with sections and questions
- **WHEN** an authenticated user navigates to `/editor/surveys/<uuid>/`
- **THEN** the left sidebar shows the pinned "Survey settings" entry followed by all sections in linked-list order, the center panel shows the first section's questions, and the right panel shows a live preview of that section

#### Scenario: Selecting a different section
- **WHEN** the user clicks a section in the sidebar
- **THEN** the center panel updates via HTMX to show that section's detail form and questions, and the preview iframe refreshes to show that section
