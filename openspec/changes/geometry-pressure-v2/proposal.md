## Why

The current `geometry-pressure` implementation (v1) stores all predefined shapes in a single Question's `geometries` JSONField with shared sub-questions across all shapes. This doesn't match the real-world use case: **each shape needs its own content** — unique text, images, and potentially different sub-questions.

Typical scenario: a festival map with 20+ zones where each zone has its own description, photos, and feedback questions. The "Main Stage" zone shows a schedule and asks about sound quality, while the "Food Court" shows a menu and asks about food quality and cleanliness.

Creating each shape as a separate question manually through the editor modal is tedious for dozens of shapes. And importing existing geometry (country borders, city districts, complex building footprints) is impossible.

**This change replaces the v1 approach**: each shape becomes a full `Question` with its own `GeometryField`, its own sub-questions, and its own content. A new section-level map editor enables bulk creation, drawing, and import of shapes.

## What Changes

- **Each shape = separate Question** — instead of a `geometries` JSONField array on one Question, each predefined shape is its own `Question` with `input_type="pressure"`. The Question's existing fields (`name`=label, `color`, `icon_class`) describe the shape. A new `GeometryField` stores the shape's geometry (Point, LineString, or Polygon).

- **Per-shape sub-questions** — each pressure Question has its own sub-questions via the existing `parent_question_id` hierarchy. Shape "Main Stage" can have `html` + `rating` + `text` sub-questions, while "Parking" has only `choice` + `text`. No more shared sub-questions limitation.

- **`geometry_id` on Answer is no longer needed** — since each shape IS a Question, `Answer.question` directly identifies the shape. The `geometry_id` field from v1 becomes obsolete.

- **`geometries` JSONField on Question is no longer needed** — replaced by the singular `GeometryField` per Question. The v1 field becomes obsolete.

- **`GeometryField` on Question** — uses GeoDjango's `GeometryField` (not JSONField) to enable future spatial queries (e.g., constraining a point question to fall within a pressure polygon). Stores any geometry type: Point, LineString, Polygon.

- **Section-level map editor** — a new editor UI at the section level that shows all pressure questions of the section on a single Leaflet map. Supports drawing new shapes (each creates a Question), editing existing shapes, bulk operations, and importing from geo files.

- **Bulk sub-questions** — select multiple shapes and add the same sub-question to all of them at once. Each shape gets its own copy of the sub-question (not a shared reference), so individual shapes can later be customized.

- **Geo format import** — upload GeoJSON or KML files to bulk-create pressure Questions. Each feature in the file becomes a separate Question with geometry and optionally mapped properties (name, color).

- **Respondent experience** — unchanged from v1 concept: predefined shapes rendered as non-editable Leaflet layers, click opens popup with that shape's sub-questions. Visual feedback for answered/unanswered shapes.

## Capabilities

### New Capabilities

- `geometry-pressure-v2`: Pressure question type where each predefined shape is a separate Question with its own `GeometryField` and per-shape sub-questions. Replaces the v1 approach of `geometries` JSONField with shared sub-questions.

- `section-map-editor`: Section-level map editor for bulk creation and management of pressure Questions. Features: draw shapes on map (each creates a Question), edit shape properties, delete shapes, bulk add sub-questions to selected shapes, import from GeoJSON/KML.

### Modified Capabilities

- `survey-editor`: Section view gains a "Map Editor" button/panel for sections containing pressure questions. Individual pressure question editing still works through the existing question modal (now with a geometry picker instead of the geometries panel).

- `survey-serialization`: Export/import handles the new `geometry` GeometryField on Question. The `geometries` JSONField and `geometry_id` on Answer are deprecated.

## Impact

- **Models**: `Question` — add `geometry` GeometryField (nullable); deprecate `geometries` JSONField. `Answer` — deprecate `geometry_id` CharField. `INPUT_TYPE_CHOICES` — `pressure` type already exists from v1.
- **Forms**: `forms.py` — update `PressureField`/`PressureButtonWidget` to work with per-Question geometry instead of geometries array. Widget carries single geometry + question metadata.
- **Views**: `views.py` — update pressure answer saving/loading to work without `geometry_id` (Answer.question identifies the shape). Render all pressure Questions in a section as map layers.
- **Editor views**: `editor_views.py` — new section-level map editor endpoints: list/create/update/delete pressure questions in bulk, import from geo files, bulk add sub-questions.
- **Templates**: new `editor/partials/section_map_editor.html` for the section-level map editor. Update `pressure_button.html` to use single geometry.
- **JavaScript**: section map editor with Leaflet Draw + shape list + import UI. Update respondent-side JS to render pressure Questions (not geometries array).
- **Serialization**: `serialization.py` — serialize `geometry` GeometryField on Question (as GeoJSON). Remove `geometry_id` from answer serialization.
- **Migration**: add `Question.geometry` GeometryField. Data migration to convert existing `geometries` JSONField entries to separate Questions (if any data exists).
