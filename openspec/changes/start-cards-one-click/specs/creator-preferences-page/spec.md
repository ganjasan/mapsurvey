## ADDED Requirements

### Requirement: Personal Preferences page
The system SHALL serve `/editor/account/` to any signed-in creator, independent of their role
in the active organization, as the place for settings that belong to the person rather than
the workspace. Anonymous visitors SHALL be redirected to the login page. The page SHALL offer
the default way to start a new survey as one choice among *Ask every time* (`''`),
*Start from scratch* (`blank`) and *Draft with AI* (`ai`), preselected from
`CreatorPreferences.survey_start_default` (no row = *Ask every time*). Submitting the form
(POST) SHALL store the chosen value, creating the `CreatorPreferences` row when missing, show
a confirmation and redirect back to the page. A value outside the three SHALL be refused with
400 and leave the stored value unchanged. When no LLM provider is configured, *Draft with AI*
SHALL be shown disabled with an explanation, and a stored `ai` SHALL still be shown as the
current value.

#### Scenario: Page shows the current default
- **WHEN** a creator with `survey_start_default='blank'` opens `/editor/account/`
- **THEN** *Start from scratch* is the selected option

#### Scenario: No preferences row yet
- **WHEN** a creator without a `CreatorPreferences` row opens the page
- **THEN** *Ask every time* is selected and nothing is written

#### Scenario: Saving a default
- **WHEN** a creator posts `survey_start_default=ai`
- **THEN** the stored value is `ai`, the response redirects to `/editor/account/`, the next page shows a confirmation, and the dashboard's "+ New Survey" links to the create page

#### Scenario: Back to asking
- **WHEN** a creator with a default posts `survey_start_default=` (empty)
- **THEN** the stored value is `''` and "+ New Survey" links to the start page again

#### Scenario: Invalid value
- **WHEN** a creator posts `survey_start_default=agent`
- **THEN** the response is 400 and the stored value is unchanged

#### Scenario: Viewer can store a default
- **WHEN** a creator whose role in the active organization is `viewer` opens and submits the page
- **THEN** the page renders and the value is stored

#### Scenario: Anonymous visitor
- **WHEN** a visitor who is not signed in opens `/editor/account/`
- **THEN** the response redirects to the login page

### Requirement: Preferences in the account menu
The system SHALL put a "Preferences" entry linking to `/editor/account/` in every account
menu shown to signed-in creators: the editor header's account menu, the editor's
organization/account dropdown, and the dashboard's account menu in `base.html`.

#### Scenario: Dashboard menu
- **WHEN** a signed-in creator opens the dashboard
- **THEN** the account menu contains a "Preferences" link to `/editor/account/`

#### Scenario: Editor menu
- **WHEN** a signed-in creator opens a survey in the editor
- **THEN** the account menu contains a "Preferences" link to `/editor/account/`
