## ADDED Requirements

### Requirement: Imported geometry is reduced to two dimensions

Layer import SHALL discard the third and any further ordinate while preserving longitude
and latitude, so a 3D file imports rather than failing. The reduction SHALL happen during
upload validation, so every ingestion path — interactive upload, single-object create, and
ZIP import — inherits it.

QGIS and ArcGIS export GeoJSON with a Z ordinate by default, and `LayerObject.geometry`
is a two-dimensional column, so such a file used to pass validation and die at the
database.

Elevation SHALL NOT be stored; nothing in the product reads it. When a file carried Z,
the import report SHALL say so, so a creator who expected elevation to survive learns
that it did not.

#### Scenario: A 3D GeoJSON imports

- **WHEN** an owner uploads a FeatureCollection whose coordinates are `[6.96, 50.94, 58.2]`
- **THEN** the layer is created, its objects carry `POINT(6.96 50.94)`, and the response reports success

#### Scenario: The creator is told Z was dropped

- **WHEN** the uploaded file carried a Z ordinate
- **THEN** the import report names that elevation was discarded

#### Scenario: Two-dimensional files are unaffected

- **WHEN** an owner uploads a FeatureCollection whose coordinates are `[6.96, 50.94]`
- **THEN** the stored geometry is identical to what the previous behaviour produced

### Requirement: A failed layer upload leaves nothing behind

Layer creation and object creation SHALL be one atomic unit: if object creation fails for
any reason, no layer row SHALL survive.

The endpoint creates the `SurveyMapLayer` row before building its objects, so a failure
during object creation used to leave an empty layer that counted against the per-survey
cap until the creator noticed it in the Reference layers card and deleted it by hand.

A failure SHALL reach the browser as the endpoint's JSON error contract with a
human-readable reason, never as an HTML error page — the JavaScript parses the response
as JSON, so an HTML 500 surfaces to the creator as `Unexpected token '<'`.

#### Scenario: Object creation fails

- **WHEN** an upload passes validation but object creation raises
- **THEN** no `SurveyMapLayer` row exists for that attempt and the per-survey layer count is unchanged

#### Scenario: The creator reads a sentence, not a parse error

- **WHEN** an upload is refused for any reason
- **THEN** the response is JSON carrying a human-readable reason, and the editor shows that reason

#### Scenario: The cap is not consumed by failures

- **WHEN** a creator makes six failed upload attempts against a survey holding four layers
- **THEN** the survey still holds four layers and a valid upload still succeeds
