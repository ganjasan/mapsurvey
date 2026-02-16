## MODIFIED Requirements

### Requirement: Dashboard integration
The system SHALL wire the "New Survey" button in `/editor/` to navigate to `/editor/surveys/new/`. The "Edit" link for each survey SHALL navigate to `/editor/surveys/<uuid>/`. Draft copies (surveys with `published_version` set) and archived versions (`is_canonical=False`) SHALL NOT appear in the dashboard table.

#### Scenario: New Survey button navigates to creation form
- **WHEN** the user clicks "New Survey" on the dashboard
- **THEN** the browser navigates to `/editor/surveys/new/`

#### Scenario: Edit link navigates to editor
- **WHEN** the user clicks "Edit" for a survey on the dashboard
- **THEN** the browser navigates to `/editor/surveys/<uuid>/`

#### Scenario: Draft copies and archived versions hidden from dashboard
- **WHEN** the dashboard lists surveys
- **THEN** surveys with `published_version` set OR `is_canonical=False` SHALL be excluded

#### Scenario: Dashboard shows version number
- **WHEN** the dashboard lists a published survey with `version_number=3`
- **THEN** the row SHALL display "v3" next to the survey name

## ADDED Requirements

### Requirement: Published surveys are read-only in the editor
The system SHALL block all structural edits (section CRUD, question CRUD, reorder, choices editing, translation editing) on surveys with `status` in (`published`, `closed`). Settings edits (name, visibility, languages, redirect_url) SHALL remain allowed. The editor SHALL display a read-only indicator and prompt the owner to create a draft copy for edits.

#### Scenario: Block question creation on published survey
- **WHEN** an editor tries to create a question on a published survey
- **THEN** the system SHALL return 403

#### Scenario: Block section creation on published survey
- **WHEN** an editor tries to create or delete a section on a published survey
- **THEN** the system SHALL return 403

#### Scenario: Block reorder on published survey
- **WHEN** an editor tries to reorder sections or questions on a published survey
- **THEN** the system SHALL return 403

#### Scenario: Allow settings edit on published survey
- **WHEN** an editor changes the name or visibility of a published survey
- **THEN** the change SHALL be applied normally

#### Scenario: Draft and testing surveys remain fully editable
- **WHEN** an editor opens a survey with `status='draft'` or `status='testing'`
- **THEN** all editor operations SHALL work normally

#### Scenario: Read-only visual indicator
- **WHEN** the editor loads a published survey
- **THEN** the editor SHALL display a "Read-only" banner and hide structural edit controls

### Requirement: Editor version and draft indicators
The system SHALL display version and draft status information in the editor header bar.

#### Scenario: Published survey shows version
- **WHEN** the editor loads a published survey with `version_number=2`
- **THEN** the header bar SHALL display "v2" badge

#### Scenario: Draft copy shows draft indicator
- **WHEN** the editor loads a draft copy (has `published_version` set)
- **THEN** the header bar SHALL display "Draft of <original name>" indicator and "Publish Version" and "Discard Draft" buttons

#### Scenario: Published survey with active draft shows link
- **WHEN** the editor loads a published survey that has an active draft copy
- **THEN** a banner SHALL appear with link to the draft copy's editor

### Requirement: Edit Published Survey action
The system SHALL provide an "Edit Published Survey" button in the editor header for published surveys without an active draft. Clicking it SHALL create a draft copy and redirect to the draft's editor.

#### Scenario: Button visible for published surveys without draft
- **WHEN** the editor loads a published survey with no active draft and the user is the owner
- **THEN** an "Edit Published Survey" button SHALL appear

#### Scenario: Button hidden for non-published surveys
- **WHEN** the editor loads a draft or testing survey
- **THEN** the "Edit Published Survey" button SHALL NOT appear

#### Scenario: Button hidden when draft exists
- **WHEN** the editor loads a published survey that already has a draft copy
- **THEN** the button SHALL NOT appear (replaced by link to draft)

### Requirement: Publish Version confirmation
The system SHALL show a confirmation modal before publishing a draft copy. If breaking compatibility issues are found, the modal SHALL display them and offer a force-publish option.

#### Scenario: Publish compatible draft
- **WHEN** the owner clicks "Publish Version" on a compatible draft
- **THEN** a modal SHALL confirm: "Publish as v{N}? Active respondents will continue on the current version."

#### Scenario: Publish incompatible draft
- **WHEN** the owner clicks "Publish Version" on a draft with breaking issues
- **THEN** the modal SHALL display the issues and offer "Force Publish" and "Cancel"

### Requirement: Discard Draft confirmation
The system SHALL show a confirmation modal before discarding a draft copy.

#### Scenario: Discard confirmation
- **WHEN** the owner clicks "Discard Draft"
- **THEN** a modal SHALL confirm: "Discard this draft? All changes will be lost."

### Requirement: Version history and export UI
The system SHALL display version history in the editor and provide version-filtered download options.

#### Scenario: Version history list
- **WHEN** the editor loads a canonical survey with archived versions
- **THEN** a version history section SHALL show all versions with version number, publish date, and session count

#### Scenario: Version-filtered download
- **WHEN** the user clicks download on a survey with multiple versions
- **THEN** a version selector SHALL appear with options: "Latest", "v1", "v2", ..., "All"
