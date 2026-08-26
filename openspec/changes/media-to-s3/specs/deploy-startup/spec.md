## ADDED Requirements

### Requirement: No mounted disk blocks instance replacement

The deploy path SHALL NOT depend on storage that attaches to one instance at a time. With media in
object storage, a new instance SHALL be able to start and pass its health check while the previous
instance is still serving traffic.

#### Scenario: A deploy no longer requires stopping the old instance first

- **WHEN** a new version is deployed
- **THEN** nothing in the service definition forces Render to stop the running instance before the
  replacement starts

#### Scenario: Media is reachable from an instance that never held it

- **WHEN** a freshly started instance serves a page referencing a previously uploaded image
- **THEN** the image resolves
- **AND** the instance read it from object storage rather than from a local mount
