## MODIFIED Requirements

### Requirement: KML export is one file with a container per question

`format=kml` SHALL return one `.kml` whose root document is named after the survey and holds one
named container (a `Document` with the LIBKML driver, a `Folder` with the KML driver) per geo
question in scope, with sub-question answers as feature data. Invalid geometries (e.g. a
self-intersecting polygon) SHALL be repaired for KML only, so one respondent's shape never fails or
empties the export. Other formats keep geometries as drawn.

#### Scenario: Containers per question
- **WHEN** a survey with two geo questions is exported as kml
- **THEN** the file parses as XML, its root is named after the survey, and it contains two
  `Document` or `Folder` elements named after the questions holding the features

#### Scenario: Self-intersecting polygon
- **WHEN** a polygon question has one self-intersecting answer and one valid answer, and the survey
  is exported as kml
- **THEN** the response is 200, and both placemarks carry geometry
- **AND** the same survey exported as gpkg keeps the self-intersecting polygon unchanged
