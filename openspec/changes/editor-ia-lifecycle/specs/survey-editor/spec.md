## ADDED Requirements

### Requirement: Lifecycle spaces navigation
The survey-management navbar SHALL present three spaces of equal rank — **Build** (survey construction), **Results** (responses & analysis), and **Publish** (public results page) — as the only tabs. The underlying routes and view names SHALL be unchanged (`editor_survey_detail`, `editor_survey_analytics`, `editor_survey_public_results`). `Share` and `Preview` SHALL be navbar action dropdowns rather than tabs, and survey settings SHALL be reachable via a ⚙ button that opens the in-Build settings panel; there SHALL be no standalone Settings tab.

#### Scenario: Three spaces shown
- **WHEN** an editor opens any survey-management page
- **THEN** the tab row shows exactly Build, Results, and Publish, with the current space marked active

#### Scenario: Share and Preview are actions
- **WHEN** the editor opens the `Share` dropdown
- **THEN** it offers to copy the survey link, show a QR code, open tracking links, and (when the results page is live) copy the results-page link
- **AND** the `Preview` dropdown offers the survey as a respondent and the results page

#### Scenario: Settings via gear
- **WHEN** the editor clicks the ⚙ button
- **THEN** the Build space opens with the survey-settings panel selected (equivalent to `?panel=settings`), and no Settings tab is present in the navbar

### Requirement: Unified publishing widget
The navbar SHALL provide a single publishing widget (the status chip) that, for owners, opens a dropdown grouping: Collection (survey status transitions), Discovery (public-gallery visibility), Results page (live state and link), and Version (version number and draft actions). The widget SHALL be presentation over existing fields (`status`, `visibility`, `PublicResultsPage.is_published`) and SHALL NOT introduce new lifecycle states. The widget SHALL appear consistently across the Build, Results, and Publish spaces.

#### Scenario: Widget groups the publish controls
- **WHEN** an owner opens the publishing widget on a published survey
- **THEN** it shows the collection status with transition actions, a gallery-visibility toggle, the results-page state with its `/r/<slug>/` link, and the version/draft section

#### Scenario: Gallery visibility toggle
- **WHEN** an owner toggles "Listed in public gallery" on
- **THEN** the survey `visibility` becomes `public`; toggling off sets it `private`; no other field changes

#### Scenario: Non-owner sees a static chip
- **WHEN** a non-owner opens a survey-management page
- **THEN** the status chip renders as a static badge without transition/visibility controls

### Requirement: Results space
The analytics surface SHALL be presented as the **Results** space (one of the three top-level spaces). Its existing split-pane Data workspace (where Table, Map, and Charts can be shown simultaneously in resizable panes) and the Performance report SHALL be preserved as internal sub-navigation of Results — they are NOT flattened into mutually-exclusive sidebar items, because that would remove the split-pane capability. Data download SHALL be available directly within the Results space. All analytics endpoints and behaviors SHALL be unchanged.

#### Scenario: Results is one space
- **WHEN** the editor opens the Results space
- **THEN** the navbar marks Results active and the split-pane Data workspace and Performance sub-views remain available

#### Scenario: Download from Results
- **WHEN** the editor is in the Results space
- **THEN** a "Download data" action is available without leaving the space

## MODIFIED Requirements

### Requirement: Survey settings accessible from the editor sidebar
The system SHALL show a pinned "Survey settings" entry above the section list in the Build space sidebar, styled identically to the "Page settings" pinned entry in the Publish space (shared `.sidebar-pinned`/`.sidebar-pinned-item` classes). Clicking it SHALL swap the center panel to a settings form (general fields, default map position, collaborators, password/test access) via HTMX without a full page reload, and SHALL mark the pinned entry active while clearing any active section. The general-fields form SHALL autosave on field change. Loading `/editor/surveys/<uuid>/?panel=settings` SHALL render the settings panel as the initial center-panel content with the pinned entry pre-selected. The navbar ⚙ button SHALL be the primary entry point to this panel.

#### Scenario: Open settings from the sidebar
- **WHEN** the user clicks the pinned "Survey settings" entry in the Build sidebar
- **THEN** the center panel swaps to the settings form (no full page reload), the pinned entry gets the active style, and no section item is shown as active

#### Scenario: Open settings from the navbar gear
- **WHEN** the user clicks the ⚙ button in the navbar
- **THEN** the browser opens the Build space with the settings panel selected

#### Scenario: Deep link opens settings directly
- **WHEN** the user loads `/editor/surveys/<uuid>/?panel=settings`
- **THEN** the initial center-panel content is the settings form and the pinned entry renders with the active style server-side

### Requirement: Standalone settings page remains reachable but is not linked
The standalone `/editor/surveys/<uuid>/settings/` URL and view SHALL continue to function (same template, same GET/POST behavior) for existing direct links and tests, but SHALL no longer be linked from the navbar or the dashboard cards — the ⚙ button and the in-Build panel are the entry points.

#### Scenario: Direct link to the old settings URL still works
- **WHEN** a user navigates directly to `/editor/surveys/<uuid>/settings/`
- **THEN** the standalone settings page renders as before
