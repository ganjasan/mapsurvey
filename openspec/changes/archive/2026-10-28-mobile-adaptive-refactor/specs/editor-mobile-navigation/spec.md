# editor-mobile-navigation

## ADDED Requirements

### Requirement: Two-level contextual navigation below 768px
On viewports narrower than 768px the editor SHALL present a top strip with the page tabs
(Survey, Responses, Public results) and a bottom tab bar whose items are contextual to the
active page tab: Survey and Public results SHALL both expose Structure, Edit and Preview;
Responses SHALL expose its own sub-views (Table, Map, Charts, Performance). Desktop
viewports SHALL be unaffected.

#### Scenario: Survey tab shows pane bar
- **WHEN** a creator opens the editor Survey tab at 390px width
- **THEN** a bottom tab bar with Structure, Edit and Preview is shown and exactly one pane is visible full-screen

#### Scenario: Bottom bar follows the page tab
- **WHEN** the creator switches the top strip from Survey to Responses
- **THEN** the bottom tab bar items change to Responses' sub-views

#### Scenario: Public results shares the pane vocabulary
- **WHEN** the creator opens the Public results tab at 390px width
- **THEN** the bottom tab bar shows Structure (block list), Edit (selected block config) and Preview (live public page)

#### Scenario: Desktop unchanged
- **WHEN** the editor is opened at 1280px width
- **THEN** neither the top strip variant nor the bottom tab bar is rendered and the three-pane layout matches pre-change behavior

### Requirement: Pane switching happens client-side
Switching panes via the bottom tab bar SHALL NOT trigger a full page load; the panes are
present in the DOM and toggled by client state.

#### Scenario: Switching panes keeps state
- **WHEN** the creator edits a question, switches to Preview, and returns to Edit
- **THEN** the Edit pane shows the same question without a page reload

### Requirement: Structure pane drills down
Within the Survey Structure pane, the sections list SHALL drill into a per-section question
list, and tapping a question SHALL open it in the Edit pane. A back affordance SHALL return
one level without losing pane state.

#### Scenario: Section to questions to edit
- **WHEN** the creator taps a section, then a question in it
- **THEN** the question list replaces the section list, then the Edit pane opens with that question selected

#### Scenario: Edit pane empty state
- **WHEN** the creator opens the Edit pane before any question was selected
- **THEN** the pane shows a hint to pick a question in Structure instead of an empty form

### Requirement: Reorder via drag handle only
Sections and questions SHALL be reorderable on touch devices by a long-press drag on the
dedicated handle. No auxiliary reorder buttons SHALL be rendered.

#### Scenario: Long-press drag reorders
- **WHEN** the creator long-presses a section's handle and drags it below the next section
- **THEN** the order is persisted identically to desktop drag-and-drop

### Requirement: One-row toolbar with overflow
Below 768px the editor toolbar SHALL render as a single row (back, survey title, version
chip, overflow menu). Share, Settings, Versions, Publish and account actions SHALL be
reachable from the overflow menu.

#### Scenario: Toolbar does not wrap
- **WHEN** the editor is opened at 390px width with a long survey name
- **THEN** the toolbar occupies one row, the title truncates with ellipsis, and the page has no horizontal overflow

#### Scenario: Overflow exposes publish
- **WHEN** the creator opens the overflow menu on a draft survey
- **THEN** the Publish action is available and behaves as the desktop Publish button

### Requirement: Mobile editor chrome is gated by a kill switch
The mobile navigation chrome SHALL be enabled only when the corresponding environment
flag is set; when unset, the pre-change layout is served on all viewports.

#### Scenario: Flag off serves legacy layout
- **WHEN** the flag is unset and the editor is opened at 390px width
- **THEN** the pre-change markup is rendered with no mobile chrome
