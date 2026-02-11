## Context

The `survey_section` view serves section forms. On POST, it saves answers and redirects forward. On GET, it creates a blank form with `initial={}`. The "Back" button is a plain `<a>` link (GET request), so returning to a section always shows an empty form — all previously entered data, including map markers, is lost.

Geo features live in a Leaflet `editableLayers` FeatureGroup on the client. Each feature carries `feature.properties.question_id` and sub-question values. On form submit, JavaScript serializes all layers to pipe-delimited GeoJSON strings in hidden `<input class="geo-inp">` fields. The server parses these and creates Answer records with geometry fields and child Answer records for sub-questions.

Currently, the POST handler always creates new Answer records — there is no update or delete-before-insert logic.

## Goals / Non-Goals

**Goals:**
- Pre-populate all form field types with saved answers when revisiting a section (GET)
- Restore geo features on the Leaflet map with their sub-question property data
- Prevent duplicate Answer records when a section is re-submitted

**Non-Goals:**
- Client-side draft saving (localStorage or AJAX auto-save) — out of scope
- Resuming a survey session after browser close — out of scope
- Editing individual geo features server-side — answers are replaced as a batch per section

## Decisions

### 1. Answer retrieval in the view's GET handler

Query existing answers for the current session and section's questions. Build an `initial` dict keyed by `question.code` for scalar fields, and a separate `existing_geo_answers` structure for geo fields.

**Rationale:** Scalar fields (text, number, choice, etc.) map naturally to Django form `initial` values. Geo fields cannot use `initial` because they bypass the normal form field mechanism — they are serialized by JavaScript into hidden inputs at submit time.

### 2. Scalar field prepopulation via form `initial` dict

Pass `initial={question.code: value, ...}` to `SurveySectionAnswerForm`. The form already accepts `initial` — Django's form fields render initial values automatically for TextInput, Textarea, NumberInput, RadioSelect, CheckboxSelectMultiple, and range inputs.

For choice/multichoice fields, the initial value must be a code (choice) or list of codes (multichoice) as strings, since Django's ChoiceField compares string values.

**Rationale:** Uses Django's built-in form initial value mechanism — no changes to form field construction needed.

### 3. Geo answer restoration via template JSON context variable

Serialize existing geo answers as a JSON structure and pass it to the template context as `existing_geo_answers`. The structure:

```json
{
  "Q_code": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [lng, lat]},
      "properties": {
        "question_id": "Q_code",
        "sub_q_code": ["value"]
      }
    }
  ]
}
```

JavaScript at page load iterates this structure, creates Leaflet layers (L.marker / L.polyline / L.polygon), sets `feature.properties`, binds sub-question popups, and adds them to `editableLayers`.

**Rationale:** This matches the existing data flow — the same GeoJSON format used at submit time is used for restoration. Leaflet's `L.geoJSON` can parse Feature objects, but we need to convert to editable layer types (marker, polyline, polygon) since `L.geoJSON` creates non-editable layers.

**Alternatives considered:**
- *Pre-fill hidden geo inputs and parse on client:* More complex, hidden inputs expect pipe-delimited strings which are harder to work with.
- *Server-side GeoJSON rendering into map tiles:* Overkill for editable survey answers.

### 4. Sub-question property reconstruction

For each geo Answer, query its child Answers (`parent_answer_id=answer`). Convert each child answer to the `properties` format: `{sub_question.code: [value]}` where value is extracted from the appropriate field (text, numeric, or selected_choices).

This matches the format that `$('#subquestion_form').serializeArray()` + `groupBy()` produces on the client, so popup loading code (which reads `layer.feature.properties`) works unchanged.

**Rationale:** Reuses the existing popup `onPopupOpen` logic that reads properties from the layer — no changes to popup interaction code needed.

### 5. Delete-before-insert on re-submission

Before saving answers in the POST handler, delete all existing Answer records for the current session and section's questions (including child answers via CASCADE). Then save new answers as before.

**Rationale:** Simpler than update-in-place. The Answer model has no external references beyond parent_answer_id (which cascades). The user is submitting a complete section — partial updates don't apply.

**Alternatives considered:**
- *Update existing records in-place:* Complex for geo questions where the number of features can change. Delete + re-create is simpler and equally correct.

### 6. Sub-question form prepopulation for geo popups

The `subquestions_forms` dict (built in GET handler, line 273-275) already generates sub-question form HTML. These forms are currently always empty. No change is needed here — the popup `onPopupOpen` handler already reads values from `layer.feature.properties` and populates form fields. Since we restore properties in Decision #4, popups will show saved values automatically.

**Rationale:** The existing client-side popup loading code handles this case already. No new server-side form prepopulation needed for sub-questions.

## Risks / Trade-offs

**[Multiple geo answers per question create N+1 queries]** → Mitigate with `prefetch_related` or a single query with `select_related` for child answers. The number of answers per section is small (typically <50), so this is acceptable even without optimization.

**[Delete-before-insert loses answer IDs]** → Answer IDs are internal — no external system references them. This is acceptable.

**[Large geo datasets could produce large JSON in template]** → Unlikely in practice — surveys typically have a handful of geo features per section. If needed, limit to a reasonable count.

**[Django form initial values for choice fields need string coercion]** → ChoiceField compares values as strings. Pass `str(code)` for choice fields and `[str(c) for c in codes]` for multichoice.
