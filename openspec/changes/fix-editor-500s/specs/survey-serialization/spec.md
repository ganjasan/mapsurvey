# survey-serialization Specification (delta)

## ADDED Requirements

### Requirement: Structure export reads images through the storage backend
Structure export SHALL obtain question images through Django's storage API rather than through a
filesystem path. Remote storage backends raise `NotImplementedError` for `.path`, so a path-based
read makes the export fail for every survey that has a question image once media lives off local
disk.

#### Scenario: Export succeeds under remote storage
- **WHEN** a survey with question images is exported in `structure` or `full` mode while media is served from a remote backend
- **THEN** the archive contains each image under `images/structure/` and the request succeeds

#### Scenario: An unreadable image does not abort the export
- **WHEN** a question references an image the storage backend cannot open
- **THEN** that image is omitted, an export warning names it, and the rest of the archive is written
