## ADDED Requirements

### Requirement: Spraycan questions round-trip with their brush size

The survey ZIP SHALL export a `spraycan` question with `input_type: spraycan` and its brush size
(`spray_brush`: `small`, `medium` or `large`), and import SHALL restore both. An archive whose
spraycan question has no `spray_brush` or an unknown value SHALL import with `medium` and a
report line naming the question. Responses serialization (`responses.json`) SHALL carry the cloud
as a `MULTIPOINT` WKT string and import it into `Answer.multipoint`.

#### Scenario: Brush size survives export and import
- **WHEN** a survey with a spraycan question of brush size `large` is exported and imported
- **THEN** the imported question is `spraycan` with `spray_brush = large`

#### Scenario: Missing brush size defaults with a report line
- **WHEN** an archive's spraycan question carries `spray_brush: huge`
- **THEN** the question imports with `medium` and the import report says so

#### Scenario: Responses carry the cloud as WKT
- **WHEN** responses are exported in full mode for a survey with spray clouds
- **THEN** each spraycan answer holds a `MULTIPOINT (...)` string, and re-importing restores the
  same number of dots
