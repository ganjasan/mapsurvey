## ADDED Requirements

### Requirement: Safe edits apply to a live survey in place

An editor or owner SHALL be able to save safe edits to a `published` or `closed` survey directly,
without a draft copy and without creating a new version. Safe edits are every edit that is not
structural (see next requirement).

#### Scenario: Typo fixed on a published survey
- **WHEN** an editor changes the text of a question on a published survey with responses
- **THEN** the change is saved to the live survey
- **AND** no draft copy is created and `version_number` is unchanged
- **AND** existing sessions stay on the same survey version

#### Scenario: Choice added to an answered question
- **WHEN** an editor adds a choice to a choice question that has answers
- **THEN** the change is saved to the live survey

#### Scenario: Unanswered choice removed
- **WHEN** an editor removes a choice no answer uses
- **THEN** the change is saved to the live survey

#### Scenario: Rewording an answered question warns once
- **WHEN** an editor edits the text of a question that has answers
- **THEN** the editor shows how many respondents answered the previous wording
- **AND** the save is not blocked

### Requirement: Structural edits on a live survey become unpublished changes

Structural edits — creating, deleting, reordering or pasting questions or sections, changing a
question's type, code, parent or layer binding, removing a choice that has answers, changing a
visibility rule or section order — SHALL NOT be applied to a live survey. The first such edit SHALL
offer, inline, to start unpublished changes; accepting creates the draft copy and applies the edit
there.

#### Scenario: Adding a question to a published survey
- **WHEN** an editor clicks "Add question" on a published survey with no unpublished changes
- **THEN** the editor explains that structural edits are kept as unpublished changes until published
- **AND** on confirmation a draft copy is created and opens on the same section with the
  new-question dialog open
- **AND** respondents still see the live survey unchanged

#### Scenario: The server enforces the classification
- **WHEN** a structural edit is POSTed directly against a live survey
- **THEN** it is refused (403 for structural endpoints, 422 for a structural change carried by a
  content form) and the live survey is unchanged

#### Scenario: Removing an answered option
- **WHEN** an editor removes an option that answers use from a live question
- **THEN** the edit is refused with a message pointing at unpublished changes

### Requirement: One editing surface per survey

While a survey has unpublished changes, opening its Build page SHALL show the unpublished changes,
under the survey's own name, with an "Unpublished changes" marker, "Publish changes", "Discard
changes" and a link to the live version. All Build edits SHALL go to the unpublished changes.

#### Scenario: Returning to a survey with unpublished changes
- **WHEN** the owner opens Build on a survey that has a draft copy
- **THEN** they land on the draft copy
- **AND** the title shows the survey's name, not "Draft of …"

#### Scenario: Live version is still reachable
- **WHEN** the owner follows "View live version"
- **THEN** the canonical survey's Build page renders without redirecting, read-only, with a link
  back to the unpublished changes

#### Scenario: Live edits wait while unpublished changes exist
- **WHEN** a safe edit is POSTed to the live survey while it has unpublished changes
- **THEN** it is refused, so that publishing the changes cannot silently drop it

### Requirement: The editor never shows a dead control

On a live survey, a control that cannot be used directly SHALL, when clicked on any viewport,
explain why and offer the action that makes it usable.

#### Scenario: Desktop click on a structural control
- **WHEN** a creator on desktop clicks "New section" on a live survey
- **THEN** the unpublished-changes prompt opens

### Requirement: The vocabulary is "unpublished changes", not drafts and versions

Creator-facing Build surfaces SHALL use "Edit", "Unpublished changes", "Publish changes" and
"Discard changes". "Version" SHALL appear only on Responses and export surfaces.

#### Scenario: No draft vocabulary in Build
- **WHEN** a published survey with unpublished changes is rendered in Build
- **THEN** the page does not contain "Draft new version", "Go to draft", "Draft of" or "Publish Version"

### Requirement: Kill switch

With `LIVE_SURVEY_EDITING` off, live surveys SHALL be read-only exactly as before this change.
