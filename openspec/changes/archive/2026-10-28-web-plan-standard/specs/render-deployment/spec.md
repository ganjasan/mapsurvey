# render-deployment — delta for web-plan-standard

## ADDED Requirements

### Requirement: Web service plan
The production web service SHALL run on a Render plan with at least 2 GB of memory
(`standard`), and that plan SHALL be declared in `render.yaml` rather than set in the
dashboard, because a Blueprint sync overwrites a dashboard-only plan. PR preview web
services SHALL stay on `starter` through `previewPlan`.

#### Scenario: Production web service has 2 GB
- **WHEN** the Blueprint is applied
- **THEN** the `mapsurvey` web service runs on the `standard` plan with a 2 GB memory limit

#### Scenario: Dashboard changes do not drift from the Blueprint
- **WHEN** an operator changes the web service plan in the Render dashboard only
- **THEN** the next Blueprint sync restores the plan declared in `render.yaml`
- **AND** therefore every plan change is made in `render.yaml`

#### Scenario: Previews stay on the small plan
- **WHEN** Render creates a PR preview from the Blueprint
- **THEN** the preview web service runs on `starter`
