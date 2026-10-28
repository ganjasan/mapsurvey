# render-deployment — delta for db-plan-basic-1gb

## ADDED Requirements

### Requirement: Database plan
The production database SHALL run on a Render plan with at least 1 GB of memory
(`basic-1gb`), declared in `render.yaml` rather than set in the dashboard, because a
Blueprint sync overwrites a dashboard-only plan. PR preview databases SHALL stay on
`basic-256mb` through `previewPlan`.

#### Scenario: Production database has 1 GB
- **WHEN** the Blueprint is applied
- **THEN** `mapsurvey-db` runs on the `basic-1gb` plan with a 1 GB memory limit

#### Scenario: Previews stay on the small plan
- **WHEN** Render creates a PR preview from the Blueprint
- **THEN** the preview database runs on `basic-256mb`
