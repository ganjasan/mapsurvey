## Why

Currently, geo-questions (point, line, polygon) let respondents **draw** new geometries on the map. This works well for open-ended spatial input ("show us where you walk"), but doesn't support a very common survey pattern: showing **predefined** objects on the map and collecting opinions about each one.

**Use case**: A city is redesigning a park. The survey creator draws park zones on the map — a playground, a walking path, a pond area, a dog park zone. Respondents see these zones on the map, click on one, and answer questions about it ("Do you like this zone?", "Rate its condition", "What would you improve?").

There is no way to do this today without hacking around the existing draw-based geo questions.

## What Changes

- **New `pressure` input type** — a question type where the survey creator defines geometries (points, lines, polygons) on the map, and respondents click on them to provide feedback. Each predefined shape acts as a selectable object with its own sub-questions.

- **Predefined geometries storage** — the Question model gains a `geometries` JSONField that stores an array of predefined shapes, each with: geometry (GeoJSON), label, color, icon, and an ID for answer linkage.

- **Respondent interaction** — on the survey-taking page, predefined shapes are rendered on the map as non-editable Leaflet layers. Clicking a shape opens a popup (or sidebar panel) with sub-questions for that shape. Answers are saved per shape.

- **Editor: geometry drawing tool** — in the survey editor, when creating/editing a `pressure` question, the editor shows a Leaflet map with drawing tools. The creator draws shapes, assigns labels/colors/icons, and manages the list of predefined geometries.

- **Editor: per-shape sub-questions** — sub-questions are defined once at the question level (shared across all shapes), not per-shape. This keeps the model simple — every shape gets the same set of questions.

- **Answer linkage** — each Answer for a pressure question references the specific shape via a `geometry_id` field, connecting the response to the predefined geometry.

- **Data export** — pressure question answers are exported with the geometry ID and shape label, plus GeoJSON for spatial analysis. CSV export includes a column identifying which shape each answer row belongs to.

## Capabilities

### New Capabilities

- `geometry-pressure`: New question type (`pressure`) that displays predefined geometric shapes on the map. Respondents click shapes to answer sub-questions about each one. Supports point, line, and polygon geometries. Geometries stored in Question.geometries JSONField. Answers linked via Answer.geometry_id. Editor provides Leaflet-based drawing interface for defining shapes with labels, colors, and icons.

### Modified Capabilities

- `survey-editor`: Question create/edit form gains a geometry editor panel when input_type is `pressure`. The panel shows a Leaflet map with draw tools (point/line/polygon), a shape list with label/color/icon fields per shape, and preview of how shapes will appear to respondents.

- `survey-serialization`: Export/import must handle the new `geometries` JSONField on Question and `geometry_id` on Answer. GeoJSON export for pressure questions groups features by geometry_id with shape label in properties.

## Impact

- **Models**: `Question` — add `geometries` JSONField (nullable); `Answer` — add `geometry_id` CharField (nullable, stores the predefined shape identifier); `INPUT_TYPE_CHOICES` — add `("pressure", "Geometry Pressure")`
- **Forms**: `forms.py` — new `PressureWidget` and `PressureField` for the survey-taking form; renders predefined shapes on map with click-to-answer interaction
- **Views**: `views.py` — pressure answer saving logic (link answers to geometry_id, handle sub-questions per shape); answer loading for GET (reconstruct which shapes have been answered)
- **Editor views**: `editor_views.py` — geometry editor endpoints for pressure questions (save/load geometries JSON)
- **Templates**: new `pressure_widget.html` for respondent-facing shape display; editor template/partial for geometry drawing interface
- **JavaScript**: Leaflet code for rendering non-editable predefined shapes, click handlers to open sub-question popups, visual feedback for answered/unanswered shapes
- **Serialization**: `serialization.py` — serialize/deserialize `geometries` field and `geometry_id` in answers
- **Static**: CSS for pressure shape styling, answered/unanswered visual states
