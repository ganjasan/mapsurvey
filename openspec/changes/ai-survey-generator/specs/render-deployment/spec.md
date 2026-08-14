# render-deployment Specification (delta)

## ADDED Requirements

### Requirement: AI provider environment variables
The AI generation credentials SHALL be provided via environment variables with
`sync: false` (never committed; the repo is public): `ANTHROPIC_API_KEY` on both the web
service (gates the UI panel) and the Celery worker service (makes the provider calls),
plus optional `AI_PROVIDER`, `AI_SURVEY_DRAFT_MODEL`, and `AI_REQUEST_TIMEOUT_SECONDS`
overrides. An unset key SHALL disable the feature without errors on every service.

#### Scenario: Key present on web and worker
- **WHEN** the production Blueprint is provisioned
- **THEN** `ANTHROPIC_API_KEY` is declared with `sync: false` on `mapsurvey-web` and `mapsurvey-celery`, and its value is set only via the Render dashboard

#### Scenario: Key absent
- **WHEN** a service starts without `ANTHROPIC_API_KEY`
- **THEN** the application boots normally and the AI generation feature is simply off

### Requirement: Celery worker on PR previews
The Celery worker service SHALL be enabled on PR preview environments so that
worker-dependent features (AI draft generation) are verifiable before merge. The cron
service SHALL remain excluded from previews.

#### Scenario: Preview gets a worker
- **WHEN** a PR preview environment is generated from render.yaml
- **THEN** a `mapsurvey-celery` preview instance is created alongside the web preview and processes enqueued tasks

#### Scenario: Cron stays off previews
- **WHEN** a PR preview environment is generated
- **THEN** no acquisition-sync cron service is created for the preview
