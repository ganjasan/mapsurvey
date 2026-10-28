## MODIFIED Requirements

### Requirement: The flat observations table has one row per placed feature

The export SHALL produce an observations table with one row per feature of every geo question in
the exported scope, columns in this order: `session_id`, `session_start_utc`, `session_language`,
`validation_status`, `version`, `section`, `question`, `question_code`, `geometry_type`, `lat`,
`lon`, `wkt`, then one column per distinct sub-question NAME across all geo questions (a name shared
by several questions is one column), then `mark_key`, `votes_up`, `votes_down`, `comments` when the
scope contains a shared-map question, then `dot_count`, `area_m2` when the scope contains a `spraycan`
question. A spray cloud is ONE feature: its row has `geometry_type=MultiPoint`, `lat`/`lon` equal
to the cloud's centroid, `wkt` beginning with `MULTIPOINT (`, `dot_count` holding the number of
dots and `area_m2` the area of the cloud's convex hull in square metres; both are empty on rows of
other geometry types. `lat`/`lon` SHALL be the point's
coordinates or the centroid of a line/polygon/cloud; `wkt` SHALL carry the full geometry for every
row. Cells SHALL be formatted by the same rule as the GeoJSON properties (`_answer_cell`), so the
table never disagrees with the GeoJSON.

#### Scenario: Two point questions with a shared sub-question name
- **WHEN** a survey has point questions "White squirrel" and "Fox squirrel", each with a `number`
  sub-question named "Quantity", and one session placed one point on each with quantities 2 and 1
- **THEN** the table has two rows, `question` reads "White squirrel" and "Fox squirrel", one column
  "Quantity" holds 2 and 1, and `lat`/`lon` hold each point's coordinates

#### Scenario: Polygon row carries centroid and WKT
- **WHEN** a respondent draws a polygon
- **THEN** its row has `geometry_type=Polygon`, `lat`/`lon` equal to the polygon centroid and `wkt`
  beginning with `POLYGON ((`

#### Scenario: Spray cloud row carries centroid, WKT and dot count
- **WHEN** a respondent sprays 120 dots on a spraycan question
- **THEN** its row has `geometry_type=MultiPoint`, `lat`/`lon` equal to the cloud centroid, `wkt`
  beginning with `MULTIPOINT (`, `dot_count` 120 and a positive `area_m2`, and those two are the
  last columns

#### Scenario: No spraycan in scope, no dot_count column
- **WHEN** the exported scope has point and polygon questions only
- **THEN** the table has no `dot_count` column, so existing scripts see the same columns as before

#### Scenario: Blank sub-question stays blank
- **WHEN** a feature's sub-question has no answer row
- **THEN** that cell is empty and never holds another question's value

#### Scenario: Excluded sessions are absent
- **WHEN** a session is trashed or `not_approved` and `include_all` is not set
- **THEN** none of its features appear in the table

## ADDED Requirements

### Requirement: Spray clouds export as MultiPoint in every format

The GeoJSON of a `spraycan` question (legacy ZIP and `format=zip`) SHALL contain one `MultiPoint`
feature per cloud with the sub-question properties the other geo types carry plus `dot_count` and
`area_m2`.
The GeoPackage, Shapefile and KML writers SHALL emit the question's layer with MultiPoint geometry
through the same `ogr2ogr` call as the other layers; the Shapefile layer type SHALL be
`MULTIPOINT`. The workbook's observations sheet SHALL carry the same row as the CSV table.

#### Scenario: GeoJSON feature per cloud
- **WHEN** two sessions sprayed clouds on the same spraycan question
- **THEN** the question's GeoJSON has two features of type `MultiPoint`, each with `dot_count` and
  `area_m2` properties

#### Scenario: Shapefile layer is MULTIPOINT
- **WHEN** a survey with one spraycan question is exported as shp
- **THEN** the ZIP contains the five files for that question and the `.shp` layer type is
  MULTIPOINT with one record per cloud
