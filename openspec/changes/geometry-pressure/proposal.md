## Why

Currently, geo-questions (point, line, polygon) let respondents **draw** new geometries on the map. This works well for open-ended spatial input ("show us where you walk"), but doesn't cover an equally common pattern: **presenting predefined objects on the map** and letting users interact with them — view information, leave feedback, or both.

This pattern appears across many domains:

- **Festival / event map** — stages, food courts, restrooms, entrances drawn on a venue map. Visitors tap a zone to see the schedule, description, or leave a review.
- **Park / urban space assessment** — playground, walking paths, pond area, dog park zone. Residents click a zone to rate its condition and suggest improvements.
- **Campus / facility navigation** — buildings, departments, parking lots. Users click to see info (hours, contacts) and optionally report issues.
- **Infrastructure audit** — bus stops, road segments, crosswalks. Citizens click to flag problems or rate quality.

The common thread: the survey creator **draws shapes on the map ahead of time**, attaches content (info and/or questions) to each shape, and respondents **click shapes to interact** — not draw their own.

There is no way to do this today without hacking around the existing draw-based geo questions.

## What Changes

- **New `pressure` input type** — a question type where the survey creator defines geometries (points, lines, polygons) on the map. Each shape is a clickable object that can carry **information content** (rich text, images) and/or **sub-questions** (rating, text, choice, etc.). Respondents click shapes to view content and optionally answer questions about each one.

- **Predefined geometries storage** — the Question model gains a `geometries` JSONField that stores an array of predefined shapes. Each shape has: geometry (GeoJSON), label, description/info HTML, color, icon, and a stable ID for answer linkage.

- **Dual-purpose shapes: info + feedback** — each shape can serve as:
  - **Info-only** — shows a popup/panel with description, images, schedule (no sub-questions needed)
  - **Feedback** — shows sub-questions for the user to answer
  - **Both** — info content at the top, questions below
  This makes the feature useful for both pure informational maps and survey/feedback scenarios.

- **Respondent interaction** — on the survey-taking page, predefined shapes are rendered on the map as non-editable, styled Leaflet layers. Clicking a shape opens a popup or sidebar panel. The panel shows the shape's info content (if any) and sub-questions (if any). Answers are saved per shape. Visual indicators show which shapes have been interacted with.

- **Editor: geometry drawing tool** — in the survey editor, when creating/editing a `pressure` question, the editor shows a Leaflet map with drawing tools. The creator draws shapes (points, lines, polygons), and for each shape configures: label, description/info HTML, color, icon.

- **Editor: sub-questions** — sub-questions are defined once at the question level (shared across all shapes), not per-shape. Every shape gets the same set of questions. This keeps the model simple and consistent with existing parent_question/sub-question patterns.

- **Answer linkage** — each Answer for a pressure question references the specific shape via a `geometry_id` field, connecting the response to the predefined geometry.

- **Data export** — pressure question answers are exported with the geometry ID and shape label, plus GeoJSON for spatial analysis. CSV export includes a column identifying which shape each answer row belongs to.

## Capabilities

### New Capabilities

- `geometry-pressure`: New question type (`pressure`) that displays predefined geometric shapes on the map. Each shape carries info content (description, images) and/or sub-questions. Respondents click shapes to view info and answer questions. Supports point, line, and polygon geometries. Geometries stored in Question.geometries JSONField with per-shape label, description, color, icon. Answers linked via Answer.geometry_id. Editor provides Leaflet-based drawing interface for defining and configuring shapes.

### Modified Capabilities

- `survey-editor`: Question create/edit form gains a geometry editor panel when input_type is `pressure`. The panel shows a Leaflet map with draw tools (point/line/polygon), a shape list with label/description/color/icon fields per shape, and preview of how shapes will appear to respondents.

- `survey-serialization`: Export/import must handle the new `geometries` JSONField on Question and `geometry_id` on Answer. GeoJSON export for pressure questions groups features by geometry_id with shape label in properties.

## Impact

- **Models**: `Question` — add `geometries` JSONField (nullable, stores array of shape objects with geometry, label, description, color, icon, id); `Answer` — add `geometry_id` CharField (nullable, stores the predefined shape identifier); `INPUT_TYPE_CHOICES` — add `("pressure", "Geometry Pressure")`
- **Forms**: `forms.py` — new `PressureWidget` and `PressureField` for the survey-taking form; renders predefined shapes on map, click opens info + sub-question panel
- **Views**: `views.py` — pressure answer saving logic (link answers to geometry_id, handle sub-questions per shape); answer loading for GET (reconstruct which shapes have been answered)
- **Editor views**: `editor_views.py` — geometry editor endpoints for pressure questions (save/load geometries JSON, per-shape configuration)
- **Templates**: new `pressure_widget.html` for respondent-facing shape display with info + questions panel; editor template/partial for geometry drawing and configuration interface
- **JavaScript**: Leaflet code for rendering non-editable predefined shapes, click handlers to open info/question panels, visual feedback for answered/unanswered shapes
- **Serialization**: `serialization.py` — serialize/deserialize `geometries` field and `geometry_id` in answers
- **Static**: CSS for pressure shape styling, info panel layout, answered/unanswered visual states
