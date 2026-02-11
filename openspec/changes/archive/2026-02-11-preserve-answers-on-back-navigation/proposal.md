## Why

When users navigate back to a previous survey section, all their answers — including map markers — are lost. The form always renders empty because the GET handler initializes the form with `initial={}` and never queries existing answers from the database. This is the most reported usability problem: users lose work and must re-enter everything.

## What Changes

- Load existing answers from the database when a section form is displayed via GET request
- Pre-populate text, number, choice, multichoice, range, rating, and datetime fields with saved values
- Restore previously drawn geo features (points, lines, polygons) on the Leaflet map, including sub-question property values
- Pre-select previously chosen options for choice and multichoice questions
- Handle answer updates on re-submission: update existing Answer records instead of creating duplicates

## Capabilities

### New Capabilities
- `answer-prepopulation`: Loading and displaying previously saved answers when revisiting a survey section, covering all question types including geo fields with sub-questions

### Modified Capabilities
_(none — no existing spec-level requirements change)_

## Impact

- **Views**: `survey_section()` GET handler must query `Answer` objects for the current session and section, then pass them as initial values to the form
- **Forms**: `SurveySectionAnswerForm.__init__()` must accept and apply initial answer data for all field types
- **Geo widgets**: Leaflet draw widgets and frontend JS must support rendering pre-existing geometries on map load, with their sub-question property values
- **Templates/JS**: `base_survey_template.html` and `survey_section.html` JS must initialize map layers from existing geo answers
- **Answer saving**: POST handler must detect and update existing answers rather than always creating new ones, to avoid duplicates on re-submission
