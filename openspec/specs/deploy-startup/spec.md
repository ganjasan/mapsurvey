# deploy-startup Specification

## Purpose

Keep the deploy's downtime window as short as the platform allows, by fixing where each start-up
step runs: build time for anything derived only from the source, pre-deploy for anything that must
touch the database before the new code goes live, and container start for nothing but the server
itself.

The window cannot currently be eliminated. The web service mounts a persistent disk, a Render disk
attaches to one instance at a time, and so Render must stop the old instance before starting the
new one — zero-downtime deploys are unavailable and the service is pinned to a single instance
until media moves off the disk.

## Requirements
### Requirement: Static assets are built into the image

Static assets SHALL be collected and post-processed when the Docker image is built. A running
container SHALL NOT need to collect static assets before it can serve traffic on Render.

#### Scenario: A built image already contains the static tree

- **WHEN** the image is built
- **THEN** `STATIC_ROOT` inside the image contains the collected, hashed and compressed assets
- **AND** the collected tree is owned by the `app` user that the container runs as

#### Scenario: A dangling static reference fails the build

- **WHEN** a template references a static file that does not exist
- **THEN** the image build fails
- **AND** no deploy of that commit reaches production

#### Scenario: The build needs no deploy secrets

- **WHEN** the image is built with no `SECRET_KEY`, no database and no AWS credentials in the
  environment
- **THEN** the static collection step succeeds

### Requirement: Migrations run before the serving instance is replaced

Database migrations on Render SHALL be applied by the web service's pre-deploy command, while the
previous version is still serving traffic. They SHALL NOT run as part of container start on Render.

#### Scenario: A deploy with a migration

- **WHEN** a commit containing a migration is deployed
- **THEN** the migration is applied before the current instance is stopped

#### Scenario: A failing migration leaves the site up

- **WHEN** the migration step fails
- **THEN** the deploy is aborted
- **AND** the previously deployed version continues to serve traffic

#### Scenario: Only the web service migrates

- **WHEN** the Celery worker or the acquisition cron starts on Render
- **THEN** it does not apply migrations
- **AND** it does not collect static assets

### Requirement: Local development keeps a self-contained start path

When the container runs outside Render, start-up SHALL continue to apply migrations, collect static
assets, and create the superuser from `DJANGO_SUPERUSER_*`, so that `docker compose up` requires no
additional manual step.

#### Scenario: Local stack comes up on a fresh database

- **WHEN** `docker compose up` is run against an empty database and no `RENDER` variable is set
- **THEN** migrations are applied during start-up
- **AND** the superuser is created when `DJANGO_SUPERUSER_USERNAME` is set

### Requirement: The build context excludes local artifacts

The Docker build context SHALL exclude the developer's virtualenv, collected static output, local
environment files, and version-control metadata, so that an image built locally depends only on
tracked sources.

#### Scenario: A local build ignores host artifacts

- **WHEN** the image is built on a machine that has `env/`, `staticfiles/` and `.env` present
- **THEN** none of them are copied into the image

