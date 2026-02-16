## CHANGED Requirements (from geometry-pressure)

### Requirement: Pressure question — one shape per Question
Each pressure question (`input_type="pressure"`) SHALL represent a single predefined shape on the map. The shape's geometry is stored in a `GeometryField` on the Question model. The Question's existing fields serve as shape metadata: `name` is the shape label, `color` is the shape color, `icon_class` is the marker icon (for points), `subtext` is the shape description, `image` is an optional shape image.

This replaces the v1 approach where one Question stored multiple shapes in a `geometries` JSONField.

#### Scenario: Create a pressure question with a point geometry
- **GIVEN** a section exists
- **WHEN** a Question is created with `input_type="pressure"` and `geometry=Point(30.3, 59.9)`, `name="Main Stage"`, `color="#ff0000"`, `icon_class="fas fa-music"`
- **THEN** the Question is saved with the geometry and metadata
- **AND** it represents a single clickable point on the respondent map

#### Scenario: Create a pressure question with a polygon geometry
- **GIVEN** a section exists
- **WHEN** a Question is created with `input_type="pressure"` and `geometry=Polygon(...)`, `name="Food Court"`
- **THEN** the Question is saved with the polygon geometry
- **AND** it represents a single clickable polygon on the respondent map

#### Scenario: Geometry field is null for non-pressure questions
- **GIVEN** a Question with `input_type="text"`
- **THEN** the `geometry` field is null and has no effect

### Requirement: Per-shape sub-questions
Each pressure Question SHALL have its own set of sub-questions via the existing `parent_question_id` hierarchy. Different shapes MAY have different sub-questions.

#### Scenario: Two shapes with different sub-questions
- **GIVEN** pressure Question "Main Stage" with sub-questions: `html` (schedule), `rating` (sound quality)
- **AND** pressure Question "Parking" with sub-questions: `choice` (enough spots?), `text` (comment)
- **WHEN** a respondent clicks "Main Stage"
- **THEN** the popup shows only schedule + sound quality rating
- **WHEN** the respondent clicks "Parking"
- **THEN** the popup shows only the parking choice + comment

#### Scenario: Shapes with identical sub-questions (via bulk creation)
- **GIVEN** 10 pressure Questions each with the same `rating` + `text` sub-questions (created via bulk add)
- **WHEN** a respondent clicks any shape
- **THEN** each shape shows its own copy of rating + text sub-questions
- **AND** answers are stored independently per shape

### Requirement: Respondent map rendering of pressure shapes
On the survey-taking page, when a section contains pressure questions, the system SHALL render all pressure Questions' geometries as non-editable Leaflet layers on the map. Styling uses each Question's `color` and `icon_class`.

#### Scenario: All pressure shapes appear on map
- **GIVEN** a section with 3 pressure Questions (point, line, polygon)
- **WHEN** a respondent opens the section
- **THEN** all 3 shapes are visible on the map with their configured colors and icons
- **AND** shapes are not draggable or editable

#### Scenario: Pressure shapes coexist with draw-based geo questions
- **GIVEN** a section with 2 pressure Questions and 1 regular polygon question
- **WHEN** a respondent opens the section
- **THEN** pressure shapes are non-editable layers AND the polygon draw button works independently

### Requirement: Click-to-interact with pressure shapes
When a respondent clicks a predefined shape, the system SHALL open a popup containing that shape's sub-questions. The popup SHALL show the shape's name, subtext, and image (if set) as header content, followed by interactive sub-question fields.

#### Scenario: Click shape opens its sub-question popup
- **WHEN** a respondent clicks pressure Question "Main Stage" on the map
- **THEN** a popup opens showing "Main Stage" as title, the shape's subtext, and its sub-questions

#### Scenario: Popup shows previously saved answers
- **GIVEN** a respondent previously answered sub-questions for "Main Stage"
- **WHEN** the respondent clicks "Main Stage" again
- **THEN** the popup fields are pre-populated with saved answers

#### Scenario: Different shapes maintain independent answers
- **GIVEN** a respondent rates "Main Stage" as 5 and "Parking" as 3
- **WHEN** opening each popup
- **THEN** "Main Stage" shows 5 and "Parking" shows 3

### Requirement: Visual feedback for interacted shapes
Same as v1: shapes that have been answered SHALL have a distinct visual style (full opacity, checkmark badge) vs unanswered shapes (reduced opacity).

#### Scenario: Unanswered shape
- **WHEN** a respondent has not yet clicked a shape
- **THEN** it is displayed with opacity 0.5

#### Scenario: Answered shape
- **WHEN** a respondent has submitted answers for a shape
- **THEN** opacity changes to 1.0 and a checkmark indicator appears

### Requirement: Pressure answer saving (v2 — no geometry_id)
When a respondent submits answers for a pressure shape, the system SHALL create one Answer for the pressure Question (with geometry stored in point/line/polygon field) and child Answers for each sub-question. `Answer.question` directly identifies the shape — no `geometry_id` needed.

#### Scenario: Save answers for a pressure point shape
- **WHEN** a respondent fills sub-questions for pressure Question "Entrance" (Point) and applies
- **THEN** an Answer is created with `question=<Entrance Question>`, `point=<coordinates>`
- **AND** child Answers are created for each sub-question with `parent_answer_id` set
- **AND** `geometry_id` is NOT set on any of these answers

#### Scenario: Upsert — re-answering a shape
- **WHEN** a respondent re-opens "Entrance" popup, changes the rating, and applies
- **THEN** the existing Answer for this `(survey_session, question)` is updated, not duplicated

### Requirement: Pressure question form rendering
Pressure questions SHALL NOT render as visible buttons/cards in the form. Instead, each renders as a hidden input (`<input type="hidden" class="pressure-answer-input">`). The shape is rendered on the map by JavaScript using template context data.

#### Scenario: Pressure questions are not visible as form fields
- **GIVEN** a section with 3 pressure questions and 2 text questions
- **WHEN** the form renders
- **THEN** only the 2 text questions show visible form fields
- **AND** the 3 pressure shapes appear on the map (not as form buttons)

### Requirement: Existing answer restoration for pressure
The view SHALL include pressure answers in `existing_geo_answers`. Each pressure Question produces at most one feature (one shape = one set of answers per session).

#### Scenario: Restore previous pressure answers
- **GIVEN** a respondent previously answered 2 out of 5 pressure shapes
- **WHEN** they revisit the section
- **THEN** `existing_geo_answers` contains entries for those 2 question codes
- **AND** the map shows those 2 shapes as answered (full opacity) with populated popup data

### Requirement: Pressure data export
GeoJSON export SHALL include pressure question answers. Each feature includes the shape's question name as `shape_label` in properties. CSV export SHALL include pressure sub-question answers with `question_code` and `question_name` columns identifying the shape.

#### Scenario: GeoJSON export
- **GIVEN** a survey with 3 answered pressure shapes
- **WHEN** exporting data
- **THEN** the GeoJSON file contains features with `shape_label` in properties

#### Scenario: CSV export
- **GIVEN** a survey with pressure answers
- **WHEN** exporting CSV
- **THEN** rows for pressure sub-questions include `question_code` and `question_name` identifying the shape

### Requirement: Pressure question serialization
Export/import SHALL serialize the `geometry` GeometryField as GeoJSON in the question structure. Import SHALL restore it via `GEOSGeometry`. Backward compatibility: importing v1 format with `geometries` array SHALL expand into separate Questions.

#### Scenario: Export pressure question
- **WHEN** exporting a survey with a pressure question having a polygon geometry
- **THEN** the exported JSON includes `"geometry": {"type": "Polygon", "coordinates": [...]}`

#### Scenario: Import pressure question
- **WHEN** importing a JSON with a pressure question having `"geometry": {"type": "Point", ...}`
- **THEN** the Question is created with `geometry` GeometryField populated

#### Scenario: Import v1 format with geometries array
- **WHEN** importing a JSON with a pressure question having `"geometries": [{...}, {...}]`
- **THEN** each entry in the array is expanded into a separate Question with its own geometry
