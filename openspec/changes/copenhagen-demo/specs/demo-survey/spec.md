## ADDED Requirements

### Requirement: Demo survey content
The repository SHALL contain the source of a demo survey, "Cycling in Copenhagen", that shows one capability per section and says which one in the section title.

#### Scenario: Tour order
- **WHEN** the demo is installed and opened
- **THEN** its sections SHALL appear in this order: welcome; questions that adapt (a choice question whose answer reveals a follow-up question, and a star rating); rating the creator's objects (an Objects-on-the-map question over a bridges layer with 👍/👎 and a comment); marking a place (a point question with a problem choice and a photo upload); drawing a route (a line question); seeing what others marked (an Objects-on-the-map question over a shared layer fed by the point question, with 👍/👎 and a comment)

#### Scenario: Honest framing
- **WHEN** a respondent reads the welcome section
- **THEN** it SHALL say that the survey is a Mapsurvey demo not run by the City of Copenhagen, and that the map already holds sample answers

#### Scenario: Attribution
- **WHEN** a respondent opens a bridge card
- **THEN** it SHALL credit the photo author and licence, and the layer SHALL credit OpenStreetMap contributors

### Requirement: Seeding command
A management command `seed_demo_survey` SHALL install the demo into an organisation from the repository source without network access.

#### Scenario: Fresh install
- **WHEN** `seed_demo_survey --org <slug>` runs and the organisation has no survey of that name
- **THEN** the survey SHALL be created through `import_survey_from_zip`, set to `published`, seeded with sample responses, its shared layer materialised, and a published unlisted public results page created at `/r/copenhagen-cycling-demo/`
- **AND** the command SHALL print the survey URL and the results URL

#### Scenario: Already installed
- **WHEN** the survey already exists in the organisation and `--replace` is not given
- **THEN** the command SHALL stop without changes and say so

#### Scenario: Replace
- **WHEN** `--replace` is given
- **THEN** the existing demo, its sessions and its results page SHALL be deleted before the new one is installed

#### Scenario: Codes remapped
- **WHEN** the import remaps question codes because they already exist in the database
- **THEN** sample answers SHALL still attach to the right questions

### Requirement: Sample responses are marked and removable
Every session the command creates SHALL carry the tag `sample`, and they SHALL be removable without touching real responses.

#### Scenario: Tagged
- **WHEN** the command seeds responses
- **THEN** every created session SHALL have `sample` in `tags`

#### Scenario: Removal
- **WHEN** `seed_demo_survey --org <slug> --remove-samples` runs
- **THEN** sessions tagged `sample` on the demo SHALL be deleted, sessions without the tag SHALL remain, and the shared layer SHALL be rebuilt without the removed marks
