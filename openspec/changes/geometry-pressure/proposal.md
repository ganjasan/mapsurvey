## Why

Currently, geo-questions (point, line, polygon) let respondents **draw** new geometries on the map. This works well for open-ended spatial input ("show us where you walk"), but doesn't cover an equally common pattern: **presenting predefined objects on the map** and letting users interact with them — view information, leave feedback, or both.

This pattern appears across many domains:

- **Festival / event map** — stages, food courts, restrooms, entrances drawn on a venue map. Visitors tap a zone to see the schedule, description, or leave a review.
- **Park / urban space assessment** — playground, walking paths, pond area, dog park zone. Residents click a zone to rate its condition and suggest improvements.
- **Campus / facility navigation** — buildings, departments, parking lots. Users click to see info (hours, contacts) and optionally report issues.
- **Infrastructure audit** — bus stops, road segments, crosswalks. Citizens click to flag problems or rate quality.

The common thread: the survey creator **draws shapes on the map ahead of time**, attaches content to each shape via sub-questions, and respondents **click shapes to interact** — not draw their own.

There is no way to do this today without hacking around the existing draw-based geo questions.

## What Changes

- **New `pressure` input type** — a question type where the survey creator defines geometries (points, lines, polygons) on the map. Each shape is a clickable object. Clicking a shape opens a popup with sub-questions — the same mechanism already used by point/line/polygon questions. All content (informational text, images, feedback forms) is delivered through sub-questions using existing types (`html`, `image`, `text`, `rating`, `choice`, etc.).

- **Predefined geometries storage** — the Question model gains a `geometries` JSONField that stores an array of predefined shapes. Each shape has: geometry (GeoJSON), label, color, icon, and a stable ID for answer linkage.

- **No new content model — sub-questions handle everything** — whether a shape needs to show a festival schedule (`html` sub-question), a photo (`image` sub-question), a rating form (`rating` sub-question), or a comment box (`text` sub-question) — it all works through the existing parent_question → sub-question hierarchy. This means:
  - Info-only shapes: just add `html`/`image` sub-questions
  - Feedback shapes: add `rating`/`choice`/`text` sub-questions
  - Mixed: combine both — info sub-questions appear as read-only content, input sub-questions collect answers

- **Sub-questions are shared across all shapes** — defined once at the question level, not per-shape. Every shape shows the same popup with the same sub-questions. This keeps the model simple and consistent with existing patterns.

- **Respondent interaction** — predefined shapes are rendered on the map as non-editable, styled Leaflet layers. Clicking a shape opens a popup with sub-questions (same UX as existing geo-question popups). Answers are saved per shape via `geometry_id`. Visual indicators show which shapes have been interacted with.

- **Editor: geometry drawing tool** — in the survey editor, when creating/editing a `pressure` question, the editor shows a Leaflet map with drawing tools. The creator draws shapes (points, lines, polygons), and for each shape configures: label, color, icon. Sub-questions are managed through the existing sub-question editor.

- **Answer linkage** — each Answer for a pressure sub-question references the specific shape via a `geometry_id` field, connecting the response to the predefined geometry.

- **Data export** — pressure question answers are exported with the geometry ID and shape label, plus GeoJSON for spatial analysis. CSV export includes a column identifying which shape each answer row belongs to.

## Capabilities

### New Capabilities

- `geometry-pressure`: New question type (`pressure`) that displays predefined geometric shapes on the map. Respondents click shapes to interact via sub-questions (using existing question types for both info and feedback). Supports point, line, and polygon geometries. Geometries stored in Question.geometries JSONField with per-shape label, color, icon. Answers linked via Answer.geometry_id. Editor provides Leaflet-based drawing interface for defining shapes.

### Modified Capabilities

- `survey-editor`: Question create/edit form gains a geometry editor panel when input_type is `pressure`. The panel shows a Leaflet map with draw tools (point/line/polygon), a shape list with label/color/icon fields per shape. Sub-questions are managed through the existing sub-question interface.

- `survey-serialization`: Export/import must handle the new `geometries` JSONField on Question and `geometry_id` on Answer. GeoJSON export for pressure questions groups features by geometry_id with shape label in properties.

## Impact

- **Models**: `Question` — add `geometries` JSONField (nullable, stores array of shape objects with geometry, label, color, icon, id); `Answer` — add `geometry_id` CharField (nullable, stores the predefined shape identifier); `INPUT_TYPE_CHOICES` — add `("pressure", "Geometry Pressure")`
- **Forms**: `forms.py` — new `PressureWidget` and `PressureField` for the survey-taking form; renders predefined shapes on map, click opens sub-question popup
- **Views**: `views.py` — pressure answer saving logic (link answers to geometry_id, handle sub-questions per shape); answer loading for GET (reconstruct which shapes have been answered)
- **Editor views**: `editor_views.py` — geometry editor endpoints for pressure questions (save/load geometries JSON)
- **Templates**: new `pressure_widget.html` for respondent-facing shape display; editor template/partial for geometry drawing interface
- **JavaScript**: Leaflet code for rendering non-editable predefined shapes, click handlers to open sub-question popups, visual feedback for answered/unanswered shapes
- **Serialization**: `serialization.py` — serialize/deserialize `geometries` field and `geometry_id` in answers
- **Static**: CSS for pressure shape styling, answered/unanswered visual states
