## ADDED Requirements

### Requirement: Help site static service
`render.yaml` SHALL declare a static site service `mapsurvey-help` with `rootDir: help`, a build command that installs dependencies and builds the Starlight project, `staticPublishPath: dist`, a `buildFilter` limited to `help/**`, a pinned `NODE_VERSION`, and `PUBLIC_POSTHOG_KEY` / `PUBLIC_POSTHOG_HOST` as `sync: false` variables. The service SHALL serve `help.mapsurvey.org` (custom domain added in the dashboard).

#### Scenario: Help-only change builds only the help site
- **WHEN** a commit touches files under `help/` only
- **THEN** the `mapsurvey-help` service redeploys and the Django web, worker and cron services do not

#### Scenario: Django-only change leaves the help site alone
- **WHEN** a commit touches no file under `help/`
- **THEN** the `mapsurvey-help` service does not redeploy

### Requirement: Help site has no preview environments
The `mapsurvey-help` service SHALL set `previews.generation: off`; help-site changes are reviewed locally (`npm run dev`) and reach production on merge. A build that nevertheless runs with `IS_PULL_REQUEST=true` SHALL mark every page `noindex`.

#### Scenario: Pull request builds nothing for the help site
- **WHEN** a pull request changes a file under `help/`
- **THEN** no preview of `mapsurvey-help` is created
