# Design: geometry-pressure-v2

## Overview

Replace the v1 approach (one Question with `geometries` JSONField + shared sub-questions + `geometry_id` on Answer) with a per-shape Question model. Each predefined shape is a full Question with its own `GeometryField` and its own sub-questions. A new section-level map editor enables bulk creation, import, and management.

## Model Changes

### Question model (`survey/models.py`)

1. Add field:
   ```python
   from django.contrib.gis.db import models as geomodels
   geometry = geomodels.GeometryField(null=True, blank=True, srid=4326)
   ```
   Stores a single geometry (Point, LineString, or Polygon) for pressure questions. `NULL` for all other question types.

2. `geometries` JSONField — **keep but deprecate**. Existing v1 data (if any) remains readable. A data migration converts v1 `geometries` array entries into separate Questions. No new code writes to this field.

3. `INPUT_TYPE_CHOICES` — `("pressure", _("Geometry Pressure"))` already exists from v1. No change.

4. `geo_questions()` — already includes `'pressure'`. No change.

5. Existing Question fields that double as shape metadata:
   - `name` → shape label (displayed on map, in popups, in export)
   - `color` → shape stroke/fill color on map
   - `icon_class` → Font Awesome icon for point markers
   - `image` → optional shape image (shown in popup)
   - `subtext` → shape description (shown in popup)
   - `parent_question_id` → sub-questions for this shape
   - `order_number` → controls rendering order / list order in editor

### Answer model (`survey/models.py`)

No new fields. `geometry_id` field from v1 — **keep but deprecate**. New pressure answers don't use it; `Answer.question` directly identifies the shape.

For pressure answers, the geometry is stored redundantly in `answer.point`, `answer.line`, or `answer.polygon` (matching the shape's geometry type). This follows the same pattern as existing geo questions and keeps the export pipeline consistent.

### Migration

Single migration:
1. Add `Question.geometry` GeometryField (nullable).
2. Data migration: for each Question with `input_type="pressure"` and non-empty `geometries` JSONField, create one new Question per geometry entry, copying `label→name`, `color→color`, `icon_class→icon_class`, geometry→`geometry` (converted via `GEOSGeometry`). Clone sub-questions for each new Question. Remove the `geometries` data from the original (set to `None`).

## Respondent Side

### Form Layer (`survey/forms.py`)

**Update `PressureField` and `PressureButtonWidget`**:

The widget no longer carries a `data-geometries` attribute with a JSON array. Instead, each pressure Question renders its own widget/button (one per shape). But this means the form would show N separate buttons — one per shape — which is not the desired UX.

**Alternative approach: section-level rendering.** Pressure questions are NOT rendered as individual form fields. Instead, the section template detects all pressure questions and renders them as a single map layer group. The form field for each pressure question is a hidden input that gets populated by JavaScript when the respondent interacts with the shape.

Implementation:
- `_get_form_from_input_type()` for `pressure` returns a `HiddenInput`-based field (not a visible button). The hidden field stores serialized sub-question answers as JSON.
- The template JavaScript reads all pressure questions from a template variable `pressure_questions_json` and renders them on the map.

```python
elif input_type == 'pressure':
    return forms.CharField(
        widget=forms.HiddenInput(attrs={'class': 'pressure-answer-input'}),
        required=False,
        label=False,
    )
```

### Template variable: `pressure_questions_json`

In `views.py`, build a dict of pressure questions for the section:

```python
pressure_questions = []
for question in questions:
    if question.input_type == 'pressure' and question.geometry:
        pressure_questions.append({
            'code': question.code,
            'name': question.name,
            'subtext': question.subtext,
            'color': question.color,
            'icon_class': question.icon_class,
            'geometry': json.loads(question.geometry.geojson),
            'image_url': question.image.url if question.image else None,
        })
```

### JavaScript — Respondent Side

**Shape rendering on map load:**

1. Parse `pressure_questions_json` from template.
2. For each pressure question, create a Leaflet layer:
   - Point → `L.marker` with colored Font Awesome icon
   - LineString → `L.polyline` with `color`
   - Polygon → `L.polygon` with `color` stroke, translucent fill
3. Add to a shared `pressureLayerGroup` (non-editable, separate from `editableLayers`).
4. Store question code in `layer.feature.properties.question_id`.
5. Set initial style: opacity 0.5 for unanswered shapes.

**Click handler → popup:**

Each layer gets `on('click')`:
1. Read `questionCode` from `layer.feature.properties.question_id`.
2. Build popup from `subquestions_forms[questionCode]` — each pressure question already has its own sub-question form.
3. Open popup bound to layer.
4. On popup open: populate from `layer.feature.properties` (existing answers).
5. On popup close/apply: serialize form data back to properties, update hidden input.

**Visual feedback:**

Same as v1: answered shapes get full opacity + checkmark badge. Tracked in `pressureAnswered` Set keyed by question code.

**Form submission:**

On submit, for each answered pressure question:
1. Serialize geometry + sub-question properties as a GeoJSON feature.
2. Set the corresponding hidden `pressure-answer-input` field value.

### Existing Answer Restoration

Pressure answers are loaded via `existing_geo_answers[question_code]`. Each feature has one entry (the shape's geometry + sub-question values). On load, find the matching pressure layer by question code, copy properties, mark as answered.

## View Layer (`survey/views.py`)

### POST — saving pressure answers

The pressure POST handler changes significantly:

For each pressure question in the section:
1. Check if the hidden input has data (respondent interacted with this shape).
2. If yes, parse the JSON value containing sub-question answers.
3. Upsert the parent Answer: find existing `Answer(survey_session, question)` or create new. Set the geometry field (point/line/polygon) from the Question's geometry.
4. For each sub-question answer in the JSON, upsert child Answers with `parent_answer_id`.

No `geometry_id` needed — `Answer.question` directly references the pressure Question (which IS the shape).

### GET — building existing_geo_answers

For pressure questions, the existing code path works with minor adjustments:
- Remove `geometry_id` from properties (not needed).
- Each pressure Question produces at most one feature (one shape = one set of answers).

### Context additions

Add `pressure_questions_json` to the template context (see above).

## Editor — Section-Level Map Editor

### New URL endpoints

```python
# Section map editor
path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/map-editor/',
     editor_views.editor_section_map_editor, name='editor_section_map_editor'),

# Pressure question CRUD via map editor (HTMX endpoints)
path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/pressure-questions/create/',
     editor_views.editor_pressure_create, name='editor_pressure_create'),

path('editor/surveys/<uuid:survey_uuid>/pressure-questions/<int:question_id>/update/',
     editor_views.editor_pressure_update, name='editor_pressure_update'),

path('editor/surveys/<uuid:survey_uuid>/pressure-questions/<int:question_id>/delete/',
     editor_views.editor_pressure_delete, name='editor_pressure_delete'),

# Bulk operations
path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/pressure-questions/bulk-subquestion/',
     editor_views.editor_pressure_bulk_subquestion, name='editor_pressure_bulk_subquestion'),

# Import
path('editor/surveys/<uuid:survey_uuid>/sections/<int:section_id>/pressure-questions/import/',
     editor_views.editor_pressure_import, name='editor_pressure_import'),
```

### Editor views (`survey/editor_views.py`)

**`editor_section_map_editor`** (GET):
- Renders the section map editor template.
- Passes all pressure questions for this section as `pressure_questions_json`.
- Uses a fullscreen modal or dedicated page with Leaflet map + shape list panel.

**`editor_pressure_create`** (POST):
- Receives: GeoJSON geometry, name, color, icon_class.
- Creates a Question with `input_type="pressure"`, `geometry` from GeoJSON (converted via `GEOSGeometry`), and the provided metadata.
- Auto-assigns next `order_number`.
- Returns the updated shape list partial (HTMX).

**`editor_pressure_update`** (POST):
- Receives: question_id, updated fields (name, color, icon_class, geometry).
- Updates the Question.
- Returns updated shape list item partial.

**`editor_pressure_delete`** (POST):
- Deletes the pressure Question (cascades to sub-questions and answers).
- Returns updated shape list partial.

**`editor_pressure_bulk_subquestion`** (POST):
- Receives: list of question IDs + sub-question definition (input_type, name, etc.).
- For each selected Question, creates a sub-question with `parent_question_id` set.
- Returns updated shape list partial.

**`editor_pressure_import`** (POST):
- Receives: uploaded file (GeoJSON or KML).
- Parses the file, extracts features.
- For each feature: creates a Question with geometry, maps properties to name/color if available.
- Returns updated shape list partial showing all imported shapes.

### Editor template: `editor/partials/section_map_editor.html`

Layout:
```
┌──────────────────────────────────────────────────────────────┐
│  Map Editor: {{ section.title }}                    [Close]  │
├────────────────────────────────────┬─────────────────────────┤
│                                    │ Shapes ({{ count }})    │
│         Leaflet Map                │ [Select All] [Deselect] │
│                                    │                         │
│    [Draw Point] [Draw Line]        │ ☑ ● Main Stage   [✎][✕]│
│    [Draw Polygon]                  │ ☑ ▬ Food Court   [✎][✕]│
│                                    │ ☐ ▬ Parking      [✎][✕]│
│                                    │ ...                     │
│                                    │                         │
│                                    ├─────────────────────────┤
│                                    │ Bulk actions (2 sel.)   │
│                                    │ [+ Add sub-question]    │
│                                    │ [✕ Delete selected]     │
├────────────────────────────────────┴─────────────────────────┤
│  [Import GeoJSON/KML...]                                     │
└──────────────────────────────────────────────────────────────┘
```

**Draw workflow:**
1. User clicks Draw Point/Line/Polygon → Leaflet Draw activates.
2. On `draw:created` → HTMX POST to `editor_pressure_create` with geometry + default name.
3. Shape appears in list, user edits name/color/icon inline.

**Edit workflow:**
1. Click [✎] on a shape → inline edit fields or modal for name, color, icon_class.
2. On save → HTMX POST to `editor_pressure_update`.

**Import workflow:**
1. Click [Import GeoJSON/KML...] → file picker dialog.
2. On file select → POST to `editor_pressure_import`.
3. New shapes appear in list and on map.

**Bulk sub-question workflow:**
1. Select shapes via checkboxes.
2. Click [+ Add sub-question] → modal with sub-question form (input_type, name, subtext).
3. On save → POST to `editor_pressure_bulk_subquestion` with selected IDs + sub-question data.
4. Each selected shape gets a copy of the sub-question.

### Integration with existing question modal

The existing question form modal (`question_form_modal.html`) still works for pressure questions:
- When `input_type="pressure"`, show a geometry picker (single shape, not the multi-shape geometries panel from v1).
- The geometry picker is a small Leaflet map where the user draws ONE shape.
- This path is for editing a single pressure question's geometry from the question list — the section map editor is for bulk operations.

Update the geometries-editor panel: replace multi-shape editor with single-geometry picker. Hidden input becomes `geometry_json` (single GeoJSON geometry object, not array).

## Data Export (`survey/views.py` — `download_data`)

### GeoJSON export

Pressure questions are included via `geo_questions()`. Each pressure question's answers produce features with:
- Geometry from answer.point/line/polygon (same dispatch as v1).
- Properties: question name as `shape_label`, sub-question values.
- No `geometry_id` — the question code identifies the shape.

### CSV export

Pressure sub-question answers are included in CSV:
- Column `question_code` identifies the pressure question (shape).
- Column `question_name` provides the shape label.
- Sub-question values in their own columns.

## Serialization (`survey/serialization.py`)

### Question serialization

Add `"geometry"` to `_serialize_question()`:
```python
if question.geometry:
    data["geometry"] = json.loads(question.geometry.geojson)
```

### Question import

```python
geom_data = q_data.get("geometry")
if geom_data:
    question.geometry = GEOSGeometry(json.dumps(geom_data), srid=4326)
```

### Backward compatibility

If importing a v1 export with `geometries` array, expand into separate Questions (same logic as data migration).

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Per-shape model | Each shape = Question | Enables per-shape sub-questions, uses existing hierarchy |
| Geometry storage | GeometryField (PostGIS) | Future spatial queries (e.g., point-in-polygon constraints) |
| Respondent form rendering | Hidden inputs, JS renders all shapes | Avoids N visible buttons; single map with all shapes |
| geometry_id on Answer | Deprecated, not used for new data | Answer.question directly identifies the shape |
| geometries JSONField | Deprecated, data migration converts | Backward compat for existing v1 data |
| Bulk sub-questions | Copy per shape, not shared reference | Each shape can be independently customized later |
| Editor approach | Section-level map editor (new page/modal) | Bulk operations, import, overview of all shapes |
| Single-shape editor | Geometry picker in question modal | For editing individual shape geometry |
| Import formats | GeoJSON + KML | Most common; GeoJSON native, KML via conversion |
