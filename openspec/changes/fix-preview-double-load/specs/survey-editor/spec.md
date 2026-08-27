# survey-editor — delta for fix-preview-double-load

## MODIFIED Requirements

### Requirement: Live inline preview
The system SHALL display a live preview of the currently selected section in the right panel of the editor. The preview SHALL render using the existing survey-taking templates in read-only mode (form submission disabled). The preview SHALL refresh after any edit operation.

Each user action that changes what the preview shows (opening the editor, switching sections, saving a section or question, changing the preview language) SHALL trigger exactly one preview document load — never a duplicate load of the same URL from a single action.

A preview refresh SHALL load the new document off-screen and swap it into view only once loaded; the previously rendered preview SHALL remain visible for the entire duration of the load. While a load is in flight, the preview panel SHALL show a loading indicator over the stale content; the indicator SHALL disappear when the new document is swapped in.

#### Scenario: Preview updates after adding a question
- **WHEN** the user adds a new question to a section
- **THEN** the preview iframe reloads and shows the newly added question

#### Scenario: Preview shows survey as respondents see it
- **WHEN** the preview iframe loads
- **THEN** it renders the section using the same `survey_section.html` template used for survey-taking, with form submission disabled

#### Scenario: Section switch issues a single preview load
- **WHEN** the user clicks a section in the left sidebar
- **THEN** the network log contains exactly one GET of that section's preview URL for this click

#### Scenario: Editor open issues a single preview load
- **WHEN** the editor page finishes its initial load, including the HTMX load of the first section's detail panel
- **THEN** the network log contains exactly one GET of the first section's preview URL

#### Scenario: Stale preview stays visible during a slow refresh
- **WHEN** a preview refresh is triggered and the server has not yet delivered the new document
- **THEN** the previously rendered preview remains visible (no blank iframe), overlaid with a loading indicator

#### Scenario: Loading indicator clears on completion
- **WHEN** the refreshed preview document finishes loading
- **THEN** the new content replaces the stale content and the loading indicator is no longer shown

#### Scenario: Rapid successive refreshes settle on the latest
- **WHEN** a second refresh is triggered while an earlier one is still loading
- **THEN** the preview ends up showing the most recently requested URL and the loading indicator clears after it loads
