# layers-by-question

## Why

A reference layer reaches a section's map through two unrelated doors. Survey settings hold
the layer library; the section form has a "Reference layers" checklist that writes
`SurveySection.hidden_layers`; and, since `overlay-features` (#155), an "Objects on the map"
question binds the same layer to the same section with its own settings. A creator who wants
"show existing dog bins on this map" has to know that the checklist is the answer, while a
creator who wants "let people react to each other's marks" adds a question — and the two
mechanisms then disagree: a layer can be ticked in the checklist yet not bound, or bound by a
question yet unticked (owner screenshot 2026-09-06: the "Marks" layer unticked, 0 features,
next to the question that created it).

Owner decision 2026-09-06 (variant A): **a layer is on a section's map because a question of
that section shows it, and nothing else.** An "Objects on the map" question with no
sub-questions collects nothing — it *is* the reference layer.

## What Changes

- **The section "Reference layers" checklist is removed** and `SurveySection.hidden_layers`
  goes with it (data migration first, then the column). A section's map renders exactly the
  layers bound by that section's `layer_objects` questions, in question order.
- **"Objects on the map" is the one way to put a layer on a map.** Without sub-questions it
  is a display block that collects nothing: no answered-state counter, no `min_objects`, no
  progress contribution. The type picker hint and the form say so. The form gets an
  "Upload a new layer" path so the creator never has to leave for Survey settings first.
- **Panel presentation becomes a question setting, `panel_mode`**: `list` (today's object
  list with search and chips) or `legend` (one line in the panel: swatch, name, object count,
  a toggle mirroring the Leaflet layers control). Default `list`; the data migration creates
  the converted questions as `legend`, because a checklist tick never produced a list.
- **One layer once per section**: a second question binding the same layer in a section is
  refused with the name of the question that already shows it.
- **Data migration**: for every map-layout section of every survey header (canonical,
  archived versions, draft copies — each has its own question rows) and every layer of its
  layer owner that is neither in `hidden_layers` nor already bound in that section, append a
  `layer_objects` question named after the layer, `panel_mode = legend`, `min_objects = 0`.
  Published surveys keep the maps they had; nothing goes dark on deploy.
- **ZIP import** of archives that still carry `hidden_layers` runs the same conversion, so
  old exports import to the same maps they showed. Export stops writing `hidden_layers`.
- `build_map_layers_metadata` takes the section and returns only its bound layers; the
  Responses map keeps passing no section and aggregating every layer, non-interactive.
- Survey settings layer card: the "used in" line lists sections; delete is refused while
  any question binds the layer (already the rule; the copy names sections now).

### Bugs and follow-ups found while testing (owner: they ride this branch)

- **Response table empty on a draft copy** — columns keyed on the lineage representative.
- **Objects-on-the-map questions had a table column** — always empty; removed.
- **Duration was "—" for imported sessions** — it came from event pairs the ZIP never
  carried. Timing now lives on the session row (`last_activity_at`, `end_datetime`),
  written by section submits, the page-leave beacon and the thanks page; the export carries
  it (owner decision 2026-09-06).

## Capabilities

### Modified Capabilities

- `reference-overlay-layers`: per-section visibility is defined by questions, not
  `hidden_layers`.
- `layer-objects-question`: a question without sub-questions is display-only; `panel_mode`.
- `survey-serialization`: `hidden_layers` no longer exported; imported archives convert it.
- `survey-editor`: section form loses the checklist; the Objects form gains upload-new-layer
  and the one-layer-per-section rule.

## Impact

- Model + two migrations (`Question.panel_mode`; data conversion; drop
  `SurveySection.hidden_layers`).
- `survey/layers.py`, `survey/editor_forms.py`, `survey/editor_views.py`, `survey/views.py`,
  `survey/serialization.py`, `survey/cloning.py`, section form partial, question modal,
  `layer_objects_block.html`, `reference_layers.html`, `survey_section_partial.html`,
  editor preview, `survey/tests.py`.
- Depends on `overlay-features` and `respondent-shared-map` being archived first: the
  requirements this change modifies live in their delta specs, not yet in main specs.
- No new kill switch (owner rule).
