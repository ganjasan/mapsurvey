## ADDED Requirements

### Requirement: Every site write goes through the sites service
Creating, editing, duplicating, linking, publishing, unpublishing and deleting sites, their blocks, files and survey links, rotating the review link and removing event registrations SHALL be done by `survey/services/sites.py`, which takes an `Actor` and plain values and never a request, validates blocks through `sites.clean_block`, re-screens a live site after a change and records audit rows for the lifecycle steps. The editor views SHALL NOT write those rows themselves. Creating or duplicating a site SHALL count the Sites use in the service and refuse with `SitesFeatureRequired` when the workspace has none.

#### Scenario: No request needed
- **WHEN** a caller with an Actor creates a site, adds a text block, publishes and duplicates it
- **THEN** each step succeeds without a request, the text is sanitised, and audit rows record create, publish and duplicate

#### Scenario: Refused block keeps the typing
- **WHEN** the service is asked to save a button with `javascript:alert(1)`
- **THEN** it raises a refusal carrying the field error and the posted values

#### Scenario: Views write nothing
- **WHEN** the site views module is inspected
- **THEN** it contains no direct save, create, update or delete of rows
