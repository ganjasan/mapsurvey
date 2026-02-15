## ADDED Requirements

### Requirement: Pressure question type registration
The system SHALL support a new input type `pressure` in `INPUT_TYPE_CHOICES`. The Question model SHALL accept `input_type="pressure"` for questions that display predefined geometries on the map.

#### Scenario: Create a pressure question
- **WHEN** a question is created with `input_type="pressure"`
- **THEN** the question is saved successfully and appears in the section's question list

### Requirement: Predefined geometries storage
The Question model SHALL have a `geometries` JSONField (nullable, blank) that stores an array of predefined shape objects. Each shape object SHALL have the following structure: `{"id": "<stable-uuid>", "geometry": <GeoJSON geometry>, "label": "<string>", "color": "<hex>", "icon_class": "<fa-class>"}`. The `id` field SHALL be a stable identifier used for linking answers to shapes. The `geometry` field SHALL be a GeoJSON geometry object (Point, LineString, or Polygon).

#### Scenario: Question stores point geometries
- **WHEN** a pressure question has geometries `[{"id": "a1", "geometry": {"type": "Point", "coordinates": [30.3, 59.9]}, "label": "Main Stage", "color": "#ff0000", "icon_class": "fas fa-music"}]`
- **THEN** the `geometries` JSONField is saved and retrievable with the same structure

#### Scenario: Question stores mixed geometry types
- **WHEN** a pressure question has geometries containing a Point, a LineString, and a Polygon
- **THEN** all three are stored and retrievable from the `geometries` field

#### Scenario: Geometries field is optional
- **WHEN** a non-pressure question is created (e.g., input_type="text")
- **THEN** the `geometries` field is null and has no effect on the question

### Requirement: Answer linkage to predefined shape
The Answer model SHALL have a `geometry_id` CharField (max_length=50, nullable, blank) that stores the `id` of the predefined shape the answer relates to. For pressure sub-question answers, `geometry_id` identifies which shape the respondent was interacting with.

#### Scenario: Sub-question answer references a shape
- **WHEN** a respondent answers a sub-question of a pressure question for shape "a1"
- **THEN** the Answer is created with `geometry_id="a1"` and `parent_answer_id` set to the pressure question's answer

#### Scenario: Non-pressure answers have null geometry_id
- **WHEN** a respondent answers a regular text question
- **THEN** the Answer has `geometry_id=None`

### Requirement: Respondent map rendering of predefined shapes
On the survey-taking page, when a section contains a pressure question, the system SHALL render all predefined geometries from the question's `geometries` field as non-editable Leaflet layers on the map. Each shape SHALL be styled with its configured `color`. Point shapes SHALL display as colored markers with the configured `icon_class`. Line and polygon shapes SHALL use the configured `color` for stroke/fill.

#### Scenario: Pressure shapes appear on map load
- **WHEN** a respondent opens a survey section containing a pressure question with 3 predefined shapes
- **THEN** all 3 shapes are visible on the map as non-editable layers with their configured colors and icons

#### Scenario: Predefined shapes are not draggable or editable
- **WHEN** a respondent clicks and drags a predefined shape
- **THEN** the shape does not move or change — only the map pans

#### Scenario: Shapes from multiple pressure questions coexist
- **WHEN** a section has two pressure questions, each with their own predefined shapes
- **THEN** all shapes from both questions are displayed on the map simultaneously

### Requirement: Click-to-interact with predefined shapes
When a respondent clicks a predefined shape on the map, the system SHALL open a popup containing the sub-questions of the pressure question (using the same popup mechanism as existing geo questions). The popup SHALL be pre-populated with any previously saved answers for that shape.

#### Scenario: Click shape opens sub-question popup
- **WHEN** a respondent clicks on predefined shape "Main Stage"
- **THEN** a popup opens showing all sub-questions of the pressure question (e.g., rating, text comment, html info)

#### Scenario: Popup shows previously saved answers
- **WHEN** a respondent has previously answered sub-questions for shape "a1" and clicks on shape "a1" again
- **THEN** the popup fields are pre-populated with the saved answers

#### Scenario: Different shapes maintain independent answers
- **WHEN** a respondent rates shape "a1" as 5 and shape "a2" as 3
- **THEN** opening shape "a1" popup shows rating 5, and opening shape "a2" popup shows rating 3

### Requirement: Visual feedback for interacted shapes
The system SHALL visually distinguish shapes that the respondent has interacted with (submitted answers for) from shapes that have not been interacted with. Interacted shapes SHALL have a distinct visual style (e.g., increased opacity, checkmark icon, or border change).

#### Scenario: Unanswered shape appearance
- **WHEN** a respondent has not yet clicked on a shape
- **THEN** the shape is displayed with reduced opacity or a muted style

#### Scenario: Answered shape appearance
- **WHEN** a respondent has submitted answers for a shape
- **THEN** the shape's visual style changes to indicate completion (e.g., full opacity, checkmark overlay)

### Requirement: Pressure answer saving
When a respondent submits answers in a shape's popup, the system SHALL save one Answer per sub-question, each with `geometry_id` set to the shape's `id`. The parent Answer for the pressure question itself SHALL also be created with the shape's geometry stored in the appropriate geo field (point/line/polygon based on shape type).

#### Scenario: Save answers for a point shape
- **WHEN** a respondent fills sub-questions in the popup for a Point shape "a1" and applies
- **THEN** an Answer is created for the pressure question with `point` set to the shape's coordinates and `geometry_id="a1"`, and child Answers are created for each sub-question with `geometry_id="a1"`

#### Scenario: Save answers for a polygon shape
- **WHEN** a respondent fills sub-questions for a Polygon shape "b2" and applies
- **THEN** an Answer is created for the pressure question with `polygon` set to the shape's geometry and `geometry_id="b2"`, and child Answers are created for each sub-question with `geometry_id="b2"`

#### Scenario: Update previously saved answers for a shape
- **WHEN** a respondent re-opens shape "a1" popup, changes the rating, and applies
- **THEN** the existing Answer records for shape "a1" are updated (not duplicated)

### Requirement: Pressure question in survey form
The `SurveySectionAnswerForm` SHALL handle `input_type="pressure"` by rendering a widget that displays a button/card for the pressure question (similar to existing geo draw buttons) but labeled for interaction rather than drawing. The actual shape rendering and interaction happens via JavaScript on the map.

#### Scenario: Pressure question appears in form
- **WHEN** a section form is rendered containing a pressure question named "Rate the festival zones"
- **THEN** a widget is displayed with the question title and subtitle, styled distinctly from draw buttons (no draw icon — uses a tap/click interaction icon instead)

### Requirement: Existing geo answers format for pressure
The view SHALL include pressure answers in the `existing_geo_answers` context variable. For each pressure question, the format SHALL be the same GeoJSON FeatureCollection structure used by point/line/polygon questions, with each feature's `properties` containing `geometry_id` and sub-question values.

#### Scenario: Pressure answers in existing_geo_answers
- **WHEN** a respondent revisits a section with a pressure question they previously answered for shapes "a1" and "a2"
- **THEN** `existing_geo_answers[question_code]` contains a list of GeoJSON features, one per answered shape, each with `geometry_id` in properties alongside sub-question values

## MODIFIED Requirements

### Requirement: Sub-question management for geo and pressure questions
The system SHALL allow adding, editing, and deleting sub-questions for geo-type questions (point, line, polygon) **and pressure questions**. Sub-questions SHALL have `parent_question_id` set to the parent question.

#### Scenario: Add sub-question to a pressure question
- **WHEN** the user clicks "Add Sub-question" on a pressure-type question and creates a rating sub-question
- **THEN** a Question is created with `parent_question_id` set to the pressure question, and it appears nested under the parent in the question list

#### Scenario: Sub-question button on pressure questions
- **WHEN** the question list shows a "text" question and a "pressure" question
- **THEN** only the "pressure" question has an "Add Sub-question" button (same as point/line/polygon)

### Requirement: Editor geometry drawing for pressure questions
The survey editor SHALL display a geometry editor panel when creating or editing a pressure question. The panel SHALL show a Leaflet map with drawing tools (point, line, polygon). The creator SHALL be able to draw shapes on the map, and for each shape configure: label, color, icon_class. The geometries SHALL be serialized to the Question's `geometries` JSONField on save.

#### Scenario: Draw a point shape in editor
- **WHEN** the editor user draws a point on the map and sets label "Entrance", color "#00ff00", icon "fas fa-door-open"
- **THEN** a shape object is added to the geometries list with the drawn coordinates, label, color, and icon_class

#### Scenario: Draw a polygon shape in editor
- **WHEN** the editor user draws a polygon and sets label "Food Court"
- **THEN** a shape object with the polygon GeoJSON geometry is added to the geometries list

#### Scenario: Edit an existing shape
- **WHEN** the editor user selects a shape from the list and changes its label from "Entrance" to "Main Entrance"
- **THEN** the shape's label is updated in the geometries list

#### Scenario: Delete a shape
- **WHEN** the editor user removes a shape from the list
- **THEN** the shape is removed from the geometries list and from the map

#### Scenario: Load existing geometries on edit
- **WHEN** the editor opens a pressure question that already has geometries
- **THEN** all shapes are displayed on the map and listed in the shape editor panel

### Requirement: Pressure question data export
The data export (download_data view) SHALL include pressure question answers. GeoJSON files for pressure questions SHALL group features with `geometry_id` and shape `label` in the feature properties. CSV export SHALL include a `geometry_id` column and a `geometry_label` column for pressure answers.

#### Scenario: GeoJSON export includes geometry_id
- **WHEN** exporting a survey with a pressure question that has answers for 3 shapes
- **THEN** the GeoJSON file contains 3+ features, each with `geometry_id` and `geometry_label` in properties

#### Scenario: CSV export includes shape identification
- **WHEN** exporting a survey with pressure answers to CSV
- **THEN** each row for a pressure sub-question includes `geometry_id` and `geometry_label` columns

### Requirement: Serialization of pressure questions
Export/import (serialization.py) SHALL serialize the `geometries` JSONField as-is in the question structure. Import SHALL restore geometries. Answer serialization SHALL include `geometry_id` when present.

#### Scenario: Export pressure question structure
- **WHEN** exporting a survey with a pressure question having 5 predefined shapes
- **THEN** the exported JSON includes the full `geometries` array in the question object

#### Scenario: Import pressure question with geometries
- **WHEN** importing a survey JSON containing a pressure question with a `geometries` array
- **THEN** the Question is created with the `geometries` field populated

#### Scenario: Export pressure answer with geometry_id
- **WHEN** exporting answer data for a pressure question
- **THEN** each answer object includes `"geometry_id": "<id>"` alongside existing fields
