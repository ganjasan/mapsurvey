## MODIFIED Requirements

### Requirement: Preferences in the account menu
The system SHALL put a "Preferences" entry linking to `/editor/account/` in the username menu of
the header on every page that carries the application sidebar (the dashboard and the editor
alike), and in the editor's mobile overflow menu as before.

#### Scenario: Dashboard menu
- **WHEN** a signed-in creator opens the dashboard
- **THEN** the username menu contains a "Preferences" link to `/editor/account/`

#### Scenario: Editor menu
- **WHEN** a signed-in creator opens a survey in the editor
- **THEN** the username menu contains a "Preferences" link to `/editor/account/`
