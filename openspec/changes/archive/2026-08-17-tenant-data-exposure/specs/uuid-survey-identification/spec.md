## MODIFIED Requirements

### Requirement: Dashboard and template links use UUID
All links to surveys in dashboard and editor templates SHALL use `survey.uuid` to build URLs. Public-facing templates (landing page) SHALL also use `survey.uuid` for unambiguous linking.

#### Scenario: Dashboard edit link uses UUID
- **WHEN** the editor dashboard renders a survey row
- **THEN** the "Edit" link SHALL point to `/editor/surveys/<uuid>/`

#### Scenario: Dashboard export link uses UUID
- **WHEN** the editor dashboard renders export options
- **THEN** export links SHALL point to `/editor/export/<uuid>/`

#### Scenario: Dashboard delete link uses UUID
- **WHEN** the editor dashboard renders a delete action
- **THEN** the delete form/link SHALL target `/editor/delete/<uuid>/`

#### Scenario: Landing page survey links use UUID
- **WHEN** the landing page renders survey cards
- **THEN** each card link SHALL use `/surveys/<uuid>/` for unambiguous access
