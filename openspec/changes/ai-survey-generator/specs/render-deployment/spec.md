# render-deployment Specification (delta)

## ADDED Requirements

### Requirement: AI provider environment variables
The AI generation credentials SHALL be provided via environment variables with
`sync: false` (never committed; the repo is public): the selected provider's key
(`ANTHROPIC_API_KEY` or `GEMINI_API_KEY`) on both the web service (gates the UI panel)
and the Celery worker service (makes the provider calls), plus optional
`AI_SURVEY_DRAFT_MODEL`, `GEMINI_MODEL`, and `AI_REQUEST_TIMEOUT_SECONDS` overrides.
`AI_PROVIDER` SHALL be declared in the Blueprint rather than left to the settings default,
and SHALL hold the same value on web and worker: the gate is per-provider, so a mismatch
either hides the panel while a key is present or shows a panel whose generations all fail.
An unset key for the selected provider SHALL disable the feature without errors on every
service.

#### Scenario: Provider and key present on web and worker
- **WHEN** the production Blueprint is provisioned
- **THEN** `AI_PROVIDER` carries the same value on `mapsurvey-web` and `mapsurvey-celery`, that provider's key is declared with `sync: false` on both, and the key's value is set only via the Render dashboard

#### Scenario: Key absent
- **WHEN** a service starts without a key for the selected `AI_PROVIDER`
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
