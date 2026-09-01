# survey-title-rename Specification

## Purpose

Renaming a survey from the editor header — the affordance, the save endpoint, permission and
length rules, and the surfaces where the affordance is deliberately absent.

## Requirements

### Requirement: The editor header title is editable in place
On every editor page that shows the survey name in the navbar, the name SHALL be rendered
by one shared partial. When the viewer may rename the survey, that partial SHALL present the
name as an editable control that enters edit mode on click and on keyboard activation, seeded
with the survey's current name. Confirming SHALL persist the new name and leave the header
showing the value the server returned; abandoning SHALL restore the value shown before the
edit began.

#### Scenario: Owner renames from the Survey page
- **WHEN** an owner clicks the survey name in the navbar, types a new name and presses Enter
- **THEN** the name is persisted and the header shows the new name without a page reload

#### Scenario: Rename from another editor page
- **WHEN** an owner renames from the Responses, Public results, Share or Settings page
- **THEN** the behaviour and the persisted result are the same as from the Survey page

#### Scenario: Clicking away commits the edit
- **WHEN** an owner has typed a new name and clicks elsewhere on the page
- **THEN** the new name is persisted

#### Scenario: Escape abandons the edit
- **WHEN** an owner has typed a new name and presses Escape
- **THEN** nothing is persisted and the header shows the name it had before the edit

#### Scenario: Unchanged value
- **WHEN** an owner enters edit mode and confirms without changing the text
- **THEN** no write request is sent

### Requirement: Renaming is restricted to those who may edit survey settings
Renaming SHALL require the same permission as editing survey settings. A viewer without that
permission SHALL be served a non-editable name, and the rendered page SHALL contain no
editable name control for them. The server SHALL reject a rename request from such a viewer
regardless of what the page contained.

#### Scenario: Non-owner collaborator
- **WHEN** a collaborator without settings permission opens any editor page
- **THEN** the survey name is plain text with no edit affordance

#### Scenario: Rename request without permission
- **WHEN** a rename request is made by a viewer who may not edit survey settings
- **THEN** it is refused and the survey name is unchanged

### Requirement: A draft copy's header is not renamed
A draft copy of a published survey SHALL show its "draft of the published survey" header as
non-editable text. Renaming SHALL be offered on the canonical survey header only.

#### Scenario: Editing a draft copy
- **WHEN** an owner opens the draft copy of a published survey
- **THEN** the header names the published survey and offers no rename affordance

### Requirement: The name length limit is enforced visibly
The editable control SHALL prevent typing beyond the stored field's maximum length and SHALL
show the creator how much room is left as that limit is approached. A request carrying a name
longer than the maximum SHALL be rejected with a field error, and the survey name SHALL be
left unchanged — never silently shortened. The survey settings form SHALL surface the same
limit the same way.

#### Scenario: Typing up to the limit
- **WHEN** a creator types more characters than the field allows
- **THEN** the control accepts no more than the limit and the remaining room is shown before the limit is reached

#### Scenario: Over-length rename request
- **WHEN** a rename request carries a name longer than the maximum
- **THEN** it is rejected with an error naming the field, and the stored name is unchanged

#### Scenario: Name with no letters or digits
- **WHEN** a rename request carries a name that is blank or only whitespace and punctuation
- **THEN** it is rejected with the field's existing validation message and the stored name is unchanged

### Requirement: A rename writes nothing but the name
A rename SHALL change only the survey's name. Every other survey-level setting — languages,
basemaps, visibility, redirect URL, cover image — SHALL hold the value it had before the
rename.

#### Scenario: Rename a survey with non-default settings
- **WHEN** a survey with several enabled languages, a chosen default basemap and a cover image is renamed
- **THEN** the name changes and every one of those settings is unchanged
