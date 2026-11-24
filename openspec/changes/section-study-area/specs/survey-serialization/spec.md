## ADDED Requirements

### Requirement: Section study areas ride the archive and copies
The survey archive SHALL carry `section_study_areas`: for each section whose choice is Own area or
No area, its section reference, the choice and — for an own area — the outline as GeoJSON, source,
place name, fog, refusal rule and message; refused counters SHALL stay home. Import SHALL write them
through the study area service once sections exist; an entry naming no map section of the archive or
with a broken outline SHALL become a report line, never a failed import. Duplicating a survey SHALL
copy the choices.

#### Scenario: Round trip
- **WHEN** a survey whose second section has an own area and third section has No area is exported and imported
- **THEN** the imported survey's second section uses the same own outline and rules and the third uses no area

#### Scenario: Unknown section in the archive
- **WHEN** an archive's `section_study_areas` names a section reference the archive has no map section for
- **THEN** the import succeeds, that entry is skipped and the report says so

#### Scenario: Duplicate
- **WHEN** a survey with a section on No area is duplicated
- **THEN** the copy's section of the same reference is on No area
