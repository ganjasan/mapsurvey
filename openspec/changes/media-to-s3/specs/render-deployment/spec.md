## ADDED Requirements

### Requirement: Media object storage environment variables

The Blueprint SHALL supply every service that reads or writes media with the variables needed to reach
the bucket: the enable flag, the bucket name, the bucket Region and the access credentials. Services
that touch no media SHALL NOT carry them. Credentials SHALL be declared as secrets, never as literal
values in `render.yaml`.

#### Scenario: Media variables present wherever files are written

- **WHEN** the web service or the Celery worker starts
- **THEN** the media bucket variables are present in its environment
- **AND** the credentials arrive as secrets rather than Blueprint literals

#### Scenario: A service that writes no media carries no bucket credentials

- **WHEN** a scheduled job that only reads and writes database rows starts
- **THEN** no media bucket credentials are present in its environment

#### Scenario: Preview environments get their own prefix

- **WHEN** Render creates a PR preview from the Blueprint
- **THEN** the preview's media prefix differs from the production prefix
- **AND** the prefix is derived per environment rather than declared in the Blueprint, which cannot
  know a preview service's name in advance
- **AND** the preview uses the same bucket

#### Scenario: Public repository holds no credentials

- **WHEN** `render.yaml` is read from the public repository
- **THEN** it contains no access key id and no secret access key

### Requirement: The web service mounts no disk

The web service SHALL NOT declare a persistent disk. Uploaded media lives in object storage, so no
service needs storage that attaches to a single instance.

#### Scenario: Blueprint declares no disk

- **WHEN** the Blueprint is applied
- **THEN** the web service has no `disk:` block
- **AND** no mount path is reserved for media

#### Scenario: More than one instance can serve

- **WHEN** the web service is scaled to more than one instance
- **THEN** every instance serves the same media
- **AND** no instance holds a file the others cannot see
