## ADDED Requirements

### Requirement: Section-level map editor page
The survey editor SHALL provide a section-level map editor accessible via a button on the section detail page. The editor shows a Leaflet map displaying all pressure questions in the section and a shape list panel for management.

#### Scenario: Open section map editor
- **GIVEN** a section with 5 pressure questions
- **WHEN** the editor user clicks "Map Editor" on the section detail
- **THEN** a fullscreen modal or page opens showing a Leaflet map with all 5 shapes rendered
- **AND** a shape list panel on the right shows all 5 shapes with their names, colors, and icons

#### Scenario: Section with no pressure questions
- **GIVEN** a section with only text and rating questions
- **WHEN** the editor user opens the map editor
- **THEN** the map is empty and the shape list shows "No shapes yet. Draw or import to add."

### Requirement: Draw shapes in map editor
The map editor SHALL provide Leaflet Draw tools (point, line, polygon) to create new pressure questions. Drawing a shape creates a Question with `input_type="pressure"` and the drawn geometry.

#### Scenario: Draw a point shape
- **WHEN** the editor user selects "Draw Point" and clicks on the map
- **THEN** a new pressure Question is created with `geometry=Point(...)`, `name="Shape N"` (auto-generated)
- **AND** the shape appears in the shape list with an editable name field

#### Scenario: Draw a polygon shape
- **WHEN** the editor user selects "Draw Polygon" and draws a polygon
- **THEN** a new pressure Question is created with the polygon geometry
- **AND** it appears on the map and in the shape list

#### Scenario: Auto-increment order number
- **GIVEN** a section with 3 existing pressure questions (order 1, 2, 3)
- **WHEN** a new shape is drawn
- **THEN** the new Question gets `order_number=4`

### Requirement: Edit shape properties in map editor
Each shape in the shape list SHALL have controls to edit: name (inline text input), color (color picker), icon_class (icon picker, for points). Changes are saved via HTMX requests.

#### Scenario: Rename a shape
- **WHEN** the editor user changes the name of "Shape 1" to "Main Stage"
- **THEN** the Question's `name` is updated
- **AND** the map label updates to show "Main Stage"

#### Scenario: Change shape color
- **WHEN** the editor user changes a shape's color from red to blue
- **THEN** the Question's `color` is updated
- **AND** the shape on the map re-renders with the new color

### Requirement: Delete shapes in map editor
The shape list SHALL have a delete button per shape. Deleting a shape removes the Question and cascades to its sub-questions and answers.

#### Scenario: Delete a single shape
- **WHEN** the editor user clicks delete on "Parking"
- **THEN** a confirmation prompt appears
- **AND** on confirm, the Question and its sub-questions/answers are deleted
- **AND** the shape disappears from the map and shape list

### Requirement: Select shapes for bulk operations
The shape list SHALL have checkboxes for multi-selection. A "Select All" / "Deselect All" toggle is provided. Selected count is displayed. Bulk action buttons appear when shapes are selected.

#### Scenario: Select multiple shapes
- **WHEN** the editor user checks 5 out of 10 shapes
- **THEN** the UI shows "5 selected" and bulk action buttons become active

#### Scenario: Select all
- **WHEN** the editor user clicks "Select All"
- **THEN** all shapes are checked and the count shows the total

### Requirement: Bulk add sub-question
When shapes are selected, the "Add sub-question" bulk action SHALL open a modal where the user defines a sub-question (input_type, name, subtext, etc.). On save, a copy of this sub-question is created for each selected shape.

#### Scenario: Add rating sub-question to all shapes
- **GIVEN** 10 shapes are selected
- **WHEN** the user clicks "Add sub-question", configures a `rating` type question "Rate this zone", and saves
- **THEN** 10 new sub-questions are created, one per selected shape, each with `parent_question_id` pointing to its shape's Question
- **AND** each is an independent copy (editing one doesn't affect others)

#### Scenario: Add sub-question to subset
- **GIVEN** 3 out of 10 shapes are selected
- **WHEN** the user adds a sub-question via bulk action
- **THEN** only the 3 selected shapes get the new sub-question

### Requirement: Bulk delete shapes
When shapes are selected, the "Delete selected" bulk action SHALL delete all selected pressure Questions after confirmation.

#### Scenario: Bulk delete
- **GIVEN** 5 shapes are selected
- **WHEN** the user clicks "Delete selected" and confirms
- **THEN** all 5 Questions (and their sub-questions/answers) are deleted
- **AND** they disappear from the map and shape list

### Requirement: Import shapes from GeoJSON
The map editor SHALL provide an "Import" button that accepts a GeoJSON file upload. Each Feature in the file creates a new pressure Question with the feature's geometry and optionally mapped properties.

#### Scenario: Import GeoJSON with 20 features
- **WHEN** the editor user uploads a GeoJSON FeatureCollection with 20 polygon features
- **THEN** 20 new pressure Questions are created in the section
- **AND** each has the polygon geometry from the corresponding feature
- **AND** all appear on the map and in the shape list

#### Scenario: Map GeoJSON properties to shape fields
- **GIVEN** a GeoJSON feature with `properties: {"name": "District A", "color": "#ff0000"}`
- **WHEN** imported
- **THEN** the Question's `name` is set to "District A" and `color` to "#ff0000"

#### Scenario: Features without name property
- **GIVEN** a GeoJSON feature without a `name` property
- **WHEN** imported
- **THEN** the Question's `name` is auto-generated (e.g., "Shape 1", "Shape 2")

### Requirement: Import shapes from KML
The map editor SHALL also accept KML file uploads. Each Placemark creates a pressure Question.

#### Scenario: Import KML file
- **WHEN** the editor user uploads a KML file with 5 placemarks
- **THEN** 5 new pressure Questions are created
- **AND** placemark names are used as Question names
- **AND** geometries are converted from KML to Django GeometryField format

### Requirement: Single-shape geometry editor in question modal
When editing a pressure question through the standard question form modal, the geometries editor panel SHALL show a single-geometry picker (small Leaflet map to draw/edit ONE shape) instead of the v1 multi-shape editor.

#### Scenario: Edit pressure question geometry via modal
- **GIVEN** a pressure question "Main Stage" with a point geometry
- **WHEN** the editor user opens the question edit modal
- **THEN** a small Leaflet map shows the existing point
- **AND** the user can click to move/redraw the point
- **AND** on save, the `geometry` field is updated

#### Scenario: Create pressure question via modal (without map editor)
- **WHEN** the editor user creates a new question with `input_type="pressure"` via the standard modal
- **THEN** a geometry picker appears where they can draw one shape
- **AND** on save, the Question is created with the drawn geometry

### Requirement: Map editor button on section detail
The section detail page SHALL show a "Map Editor" button that opens the section-level map editor.

#### Scenario: Map Editor button visible
- **GIVEN** a section detail page
- **WHEN** it renders
- **THEN** a "Map Editor" button is visible alongside the existing "Map Position" button
- **AND** clicking it opens the section map editor
