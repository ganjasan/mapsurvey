# Design: geometry-pressure

## Overview

Add a `pressure` question type that renders survey-creator-defined geometries on the Leaflet map and lets respondents click them to interact via sub-question popups. Reuses the existing sub-question / parent-answer hierarchy — no new content models needed.

## Model Changes

### Question model (`survey/models.py`)

1. Add `("pressure", _("Geometry Pressure"))` to `INPUT_TYPE_CHOICES` (after `"html"`).

2. Add field:
   ```python
   geometries = models.JSONField(null=True, blank=True)
   ```
   Schema: list of shape objects:
   ```json
   [
     {
       "id": "uuid-string",
       "geometry": { "type": "Point", "coordinates": [30.3, 59.9] },
       "label": "Main Stage",
       "color": "#ff0000",
       "icon_class": "fas fa-music"
     }
   ]
   ```
   The `id` is a UUID4 string generated client-side in the editor when a shape is drawn. It is the stable key for linking answers to shapes.

3. Update `geo_questions()` on SurveyHeader to also include `pressure`:
   ```python
   def geo_questions(self):
       return Question.objects.filter(
           survey_section__survey_header=self,
           input_type__in=['point', 'line', 'polygon', 'pressure']
       )
   ```

### Answer model (`survey/models.py`)

Add field:
```python
geometry_id = models.CharField(max_length=50, null=True, blank=True)
```

This links an answer (and its child sub-answers) to a specific predefined shape. For non-pressure questions it stays `None`.

### Migration

Single migration adding `Question.geometries` and `Answer.geometry_id`. Both nullable — no data migration needed.

## Form Layer (`survey/forms.py`)

### New widget: `PressureButtonWidget`

Subclass of `LeafletDrawButtonWidget`. Template: `pressure_button.html`. Differences from draw-button widgets:
- No draw-type attribute — no L.Draw handler needed.
- Button labeled with a tap/click icon (`fas fa-hand-pointer`) instead of a draw icon.
- Renders a hidden `<input>` with class `geo-inp` (same as existing geo widgets) to participate in form submission.
- Carries `data-geometries='{{ widget.geometries|escapejs }}'` attribute — the JSON array of predefined shapes — so JavaScript can render them.

### New field: `PressureField`

Subclass of `LeafletDrawButtonField`. Adds a `geometries` parameter (the JSON array) passed through to the widget via `widget_attrs`.

### `_get_form_from_input_type()` addition

```python
elif input_type == 'pressure':
    return PressureField(
        title=title, subtitle=subtitle,
        color=color, icon_class=icon_class,
        draw_icon_class='fas fa-hand-pointer',
        geometries=json.dumps(question.geometries or []),
        widget=PressureButtonWidget, required=False,
    )
```

## Template: `pressure_button.html`

Identical layout to `leaflet_draw_button.html` but:
- CSS class: `pressurebutton` instead of `drawbutton`.
- Draw-icon slot shows `fas fa-hand-pointer`.
- Hidden `<input class="geo-inp">` with `name="{{ widget.name }}"`.
- `data-geometries` attribute on button carrying the shapes JSON.
- No `draw-type` attribute.

## JavaScript — Respondent Side (`base_survey_template.html` / `survey_section.html`)

### Shape rendering on map load

After map init, find all `.pressurebutton` elements. For each:

1. Parse `data-geometries` JSON.
2. For each shape, create a Leaflet layer:
   - **Point** → `L.marker` with `L.icon.fontAwesome` using shape's `color` and `icon_class`.
   - **LineString** → `L.polyline` with `color`.
   - **Polygon** → `L.polygon` with `color` for stroke, `color + "30"` for fill.
3. Add layers to a dedicated `L.featureGroup` per question (not to `editableLayers` — these are non-editable).
4. Store `layer.feature = { type: "Feature", geometry: shape.geometry, properties: { question_id: questionCode, geometry_id: shape.id } }`.
5. Set initial style: reduced opacity (0.5) for unanswered shapes.

### Click handler → popup

Each predefined layer gets an `on('click')` handler:
1. Read `questionCode` and `geometry_id` from `layer.feature.properties`.
2. Build popup HTML using `subquestions_forms[questionCode]` (the pre-rendered sub-question form, same as existing geo popups).
3. Give the form a unique ID: `subquestion_form_<geometry_id>` (consistent with marker-popup-isolation spec).
4. Bind popup to layer and open it.
5. On popup open: populate form fields from `layer.feature.properties` (same `onPopupOpen` logic).
6. On popup close / apply: serialize form data back into `layer.feature.properties` (same `onPopupClose` pattern). Mark shape as answered.

### Visual feedback

Answered shapes: full opacity (1.0), add CSS class `pressure-answered`. For point markers, swap to a checkmark-badged icon variant (add a small `✓` overlay div inside the marker's icon div).

Unanswered shapes: opacity 0.5, muted appearance.

Tracked via a `pressureAnswered` Set per question, keyed by `geometry_id`.

### Form submission

On `$('#section_question_form').submit()`:
1. For each pressure question's featureGroup, iterate layers.
2. For layers that have been answered (properties have sub-question data), serialize to GeoJSON and append to the hidden `geo-inp` field as pipe-delimited strings (same format as existing geo questions).
3. Each GeoJSON feature includes `geometry_id` in `properties`.

This means the existing POST handler in `views.py` will receive pressure data in the same pipe-delimited GeoJSON format as point/line/polygon.

### Restoring existing answers

In the `existingGeoAnswers` restoration loop, detect pressure questions (check if `.pressurebutton` exists for that question code). Instead of creating new layers, match each existing feature to a predefined shape by `geometry_id`:
1. Find the predefined layer with matching `geometry_id`.
2. Copy properties from the existing answer into the layer's `feature.properties`.
3. Mark as answered (visual update).

## View Layer (`survey/views.py`)

### POST — saving pressure answers

The existing geo-save block (`if question.input_type in ['point', 'line', 'polygon']`) extends to include `'pressure'`:

```python
if question.input_type in ['point', 'line', 'polygon', 'pressure']:
```

Inside the loop, for pressure questions, determine the geometry type from the GeoJSON feature's `geometry.type`:
- `"Point"` → `answer.point = resultToSave`
- `"LineString"` → `answer.line = resultToSave`
- `"Polygon"` → `answer.polygon = resultToSave`

Additionally, extract `geometry_id` from `gj['properties']['geometry_id']` and set `answer.geometry_id = geometry_id`.

For sub-answer creation, also propagate `geometry_id`:
```python
sub_answer.geometry_id = geometry_id
```

**Upsert logic**: Before creating a new Answer for a pressure shape, check if an Answer with the same `(survey_session, question, geometry_id)` already exists. If so, update it rather than creating a duplicate. This handles the "edit and re-apply" flow.

### GET — building existing_geo_answers

The existing block for geo questions extends to include `pressure`. The code already builds GeoJSON features with properties — just ensure `geometry_id` is included:

```python
feature['properties']['geometry_id'] = answer.geometry_id
```

### Context: `pressure_geometries`

Pass an additional template variable `pressure_geometries_json` — a dict mapping question codes to their `geometries` JSON arrays. This is used by JS to render predefined shapes:

```python
pressure_geometries = {}
for question in questions:
    if question.input_type == 'pressure' and question.geometries:
        pressure_geometries[question.code] = question.geometries
```

Alternatively, this data can be carried on the widget's `data-geometries` attribute (see Form Layer above). Using the widget attribute is simpler — no extra context variable needed. **Decision: use widget attribute.**

## Editor — Geometry Drawing Panel

### Editor views (`survey/editor_views.py`)

In `editor_question_create` and `editor_question_edit`, after saving the question and processing `choices_json`, add processing for `geometries_json`:

```python
geometries_json = request.POST.get('geometries_json', '').strip()
if geometries_json:
    question.geometries = json.loads(geometries_json)
    question.save()
elif question.input_type == 'pressure':
    question.geometries = []
    question.save()
```

No new URL endpoints needed — the existing create/edit endpoints handle it.

### Editor template (`question_form_modal.html`)

Add a `geometries-editor` div (analogous to `choices-editor`) that is shown/hidden based on `input_type == "pressure"`:

```html
<div class="geometries-editor" id="geometries-editor" style="display:none;">
    <label>Predefined Shapes</label>
    <div id="geometries-map" style="height:300px;"></div>
    <div id="geometries-list"></div>
    <button type="button" class="btn btn-sm btn-outline-secondary" id="add-shape-btn">
        <i class="fas fa-plus"></i> Draw Shape
    </button>
</div>
<input type="hidden" name="geometries_json" id="geometries-json-input">
```

JavaScript (inline in the template, same pattern as choices editor):
1. Init a Leaflet map in `#geometries-map` when `input_type` changes to `pressure`.
2. Add L.Draw controls (marker, polyline, polygon).
3. On `draw:created`: generate a UUID, add to shapes list, render in `#geometries-list` with fields for label, color (using the existing color input pattern), icon_class (using the existing icon picker pattern).
4. On save: serialize shapes array to `#geometries-json-input`.
5. On edit of existing question: load `question.geometries` into the map and list.

Each shape row in `#geometries-list`:
```
[icon] [label input] [color input] [icon picker] [delete btn]
```

## Data Export (`survey/views.py` — `download_data`)

### GeoJSON export

The `download_data` view already iterates `geo_questions()`. Since `geo_questions()` now includes pressure, pressure answers will be exported. The geometry extraction needs a type-dispatch for pressure (since `question.input_type == "pressure"` doesn't directly tell us point/line/polygon):

```python
if geo_type == "pressure":
    if answer.point:
        coordinates = [answer.point.coords[0], answer.point.coords[1]]
        geometry_type = "Point"
    elif answer.line:
        coordinates = [[i[0], i[1]] for i in answer.line.coords]
        geometry_type = "LineString"
    elif answer.polygon:
        coordinates = [[[i[0], i[1]] for i in answer.polygon.coords[0]]]
        geometry_type = "Polygon"
```

Add `geometry_id` and `geometry_label` to properties:
```python
if answer.geometry_id and question.geometries:
    properties['geometry_id'] = answer.geometry_id
    shape = next((s for s in question.geometries if s['id'] == answer.geometry_id), None)
    if shape:
        properties['geometry_label'] = shape.get('label', '')
```

### CSV export

The CSV block currently skips geo questions (`else: continue`). Add pressure sub-question answers to the CSV:
- For each session's answers, if the answer's question is a pressure sub-question (has `geometry_id`), include it with columns `geometry_id` and `geometry_label`.

## Serialization (`survey/serialization.py`)

### Question serialization

Add `"geometries"` to `_serialize_question()`:
```python
data["geometries"] = question.geometries
```

### Question import

In the import function, when creating a Question from JSON, set `geometries`:
```python
question.geometries = q_data.get("geometries")
```

### Answer serialization

Add `"geometry_id"` to `_serialize_answer()`:
```python
data["geometry_id"] = answer.geometry_id
```

### Answer import

When creating an Answer from JSON, set:
```python
answer.geometry_id = a_data.get("geometry_id")
```

### Validation

Add `"pressure"` to `VALID_INPUT_TYPES` — this happens automatically since it's derived from `INPUT_TYPE_CHOICES`.

## Static Assets

### CSS additions (`survey/static/survey/css/`)

```css
.pressurebutton {
    /* Same base styling as .drawbutton */
}
.pressure-shape-unanswered { opacity: 0.5; }
.pressure-shape-answered { opacity: 1.0; }
.pressure-answered-badge {
    /* Small checkmark overlay on answered point markers */
}
```

### Editor CSS

```css
.geometries-editor { /* Layout for shape list + map */ }
.geometry-row { /* Per-shape row with label/color/icon fields */ }
```

## Testing

### Model tests
- Create Question with `input_type="pressure"` and `geometries` JSON — verify save/retrieve.
- Create Answer with `geometry_id` — verify save/retrieve.
- Verify `geo_questions()` includes pressure questions.

### View tests
- POST pipe-delimited GeoJSON with `geometry_id` in properties → verify Answer created with correct geo field and `geometry_id`.
- GET section with existing pressure answers → verify `existing_geo_answers` includes them with `geometry_id`.
- Upsert: POST same `geometry_id` twice → verify single Answer (updated, not duplicated).

### Export tests
- Export survey with pressure answers → verify GeoJSON contains `geometry_id` and `geometry_label`.

### Serialization tests
- Export/import round-trip preserves `geometries` on Question and `geometry_id` on Answer.

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Geometry data on widget vs context var | Widget `data-geometries` attribute | Simpler — no extra context variable, data travels with the form field |
| Shape ID format | UUID4 string, generated client-side | No server round-trip needed when drawing; stable across export/import |
| Predefined layers in editableLayers? | No — separate featureGroup per question | Prevents accidental deletion/edit; form submission iterates separately |
| Geometry type on Answer | Use existing point/line/polygon fields | No new fields needed; dispatch by checking which field is non-null |
| Upsert vs delete+recreate | Upsert (check existing by geometry_id) | Cleaner; preserves answer IDs for potential analytics |
| Sub-questions shared across shapes | Yes — same set for all shapes | Consistent with proposal; keeps model simple |
