## MODIFIED Requirements

### Requirement: The download URL accepts a format and keeps the legacy default

`GET /surveys/<slug>/download` SHALL accept `format` with values `zip`, `xlsx`, `csv`, `gpkg`, `shp`,
`kml`. With no `format` or `format=zip` the response SHALL be the legacy GeoJSON+CSV ZIP with
unchanged structure; its per-session CSV SHALL leave out empty sessions like every other format
(see "Empty sessions are never exported"). An unknown value SHALL answer 400. A GIS format on a
host without `ogr2ogr` SHALL answer 400. Authorization, `version` and `include_all` SHALL apply
identically to every format.

#### Scenario: Legacy links unchanged
- **WHEN** a client requests `/surveys/<uuid>/download?version=all` with no `format`
- **THEN** the response is `application/zip` containing one `.geojson` per geo question and the
  per-session CSV with the same columns as before this change, one row per non-empty session

#### Scenario: Unknown format
- **WHEN** a client requests `?format=pdf`
- **THEN** the response is 400 and nothing is exported

#### Scenario: Viewer role required for every format
- **WHEN** a signed-in user with no role on the survey requests `?format=xlsx`
- **THEN** the response is 404, as for the legacy ZIP

## ADDED Requirements

### Requirement: Empty sessions are never exported

Every format SHALL leave out empty sessions (as defined in `responses-empty-sessions`), whatever
`include_all` and `completed_only` say, through the same shared session gate that applies those
switches. The export dialog SHALL state, under its switches, that sessions without answers are not
exported.

#### Scenario: Empty session absent from every format
- **WHEN** a survey has 3 answered sessions and 2 empty ones and a creator requests
  `?format=xlsx`
- **THEN** the `sessions` sheet has 3 rows

#### Scenario: include_all does not bring them back
- **WHEN** the request has `include_all=1`
- **THEN** the 2 empty sessions are still absent, while trashed and not-approved sessions with
  answers are present

#### Scenario: Dialog says so
- **WHEN** the creator opens the export dialog
- **THEN** it states that sessions without answers are not exported
