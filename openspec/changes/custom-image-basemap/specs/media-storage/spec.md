## MODIFIED Requirements

### Requirement: Creator artwork is publicly readable
Creator artwork SHALL be anonymously readable by URL.

Images a creator authors — survey covers, question images, story covers, results-page images, and
processed survey image basemaps — SHALL be anonymously readable by URL, because they are already
shown openly on every survey and public results page. An image basemap upload that has not yet been
validated is not creator artwork and SHALL be stored on the private tier until processing replaces
it with the public copy.

#### Scenario: Artwork is publicly readable

- **WHEN** an unauthenticated client requests a stored creator image by URL
- **THEN** the object is returned

#### Scenario: Processed image basemap is publicly readable

- **WHEN** an unauthenticated client requests a survey's processed image basemap by URL
- **THEN** the object is returned

#### Scenario: A key outside the artwork prefixes is not publicly readable

- **WHEN** an unauthenticated client requests an object stored outside the creator-artwork prefixes
- **THEN** the request is denied

#### Scenario: Unvalidated basemap upload is not publicly readable

- **WHEN** an unauthenticated client requests the storage key of a basemap upload awaiting processing
- **THEN** the request is denied

### Requirement: Environments are isolated by key prefix

Every environment SHALL write media under its own key prefix, so that a preview environment cannot
read, overwrite or delete an object belonging to production. All services of one environment — the
web service and its Celery worker — SHALL resolve the same prefix, because the web hands files to the
worker through storage.

#### Scenario: A preview writes outside the production prefix

- **WHEN** a PR preview environment stores an image
- **THEN** the object key begins with that preview's own prefix
- **AND** no object under the production prefix is created, modified or deleted

#### Scenario: Production keys are stable across the migration

- **WHEN** a file that existed on the disk is requested after the move to S3
- **THEN** it resolves under the production prefix using the same relative path the database already
  stores
- **AND** no database rows were rewritten to complete the move

#### Scenario: A preview worker reads what its web service stored

- **WHEN** the web service of PR preview #N stores a file for a background task
- **THEN** the preview's Celery worker resolves the same `previews/<web service name>` prefix and finds
  the file
