## Why

A municipality's consultation arrives as "here are the ten sites we are building — what do
you think of each?", and today Mapsurvey cannot ask that: a respondent can only answer with
geometry they draw themselves, and a creator can only show their objects as a mute overlay
(FD-1). Backlog #152 is the buyer ask (Ideenkarte gap, ThINK Jena call, Sarasota MPO's
5-layer workaround), #151 is what makes it usable past a handful of objects, and the owner's
walk through the design surfaced a third gap: creators without GIS or hosting have no way to
*make* such objects at all. Owner decision 2026-09-01: ship the three as one change.

Requirements, journeys, decisions D1–D9 and mockups live in `user-stories.md` and the
`*.mockup.html` files next to this file; this proposal turns them into capabilities.

## What Changes

- **Objects become entities.** A reference layer stops being an opaque GeoJSON blob and
  becomes a container of *objects*: each has a stable key, title, category, rich-text
  description, link, geometry and ordered attachments (images, audio, documents, video —
  uploaded, or embedded by link). GeoJSON is derived from objects, not stored as the source.
  Existing FD-1 layers are migrated feature-by-feature; nothing a creator uploaded is lost.
- **New editor screen — the object editor** (`/editor/surveys/<uuid>/layers/<id>/`): three
  columns — searchable/filterable list built for hundreds of objects, map with Leaflet.draw,
  object card editor with attachments. Three ways in: draw on the map, import GeoJSON,
  import CSV with coordinates; plus content CSV and photo-folder import matched by key or
  title. Absorbs backlog FD-17 (draw overlay layer in the editor).
- **New question type `layer_objects` — "Objects on the map"** in the *Map questions* picker
  group: lists a layer's objects in the respondent panel (search, category chips, answered
  ✓, "answered N of M" counter, optional minimum), and opens an object as the **same map
  popup** respondent-drawn features use (variant A). The popup carries the object's card
  (cover, text, attachments, link) and the question's sub-questions.
- **Sub-questions become the one mechanism** for "ask about an object on the map", shared by
  geo questions and `layer_objects`. Two entry points into the same modal: a nested
  *Sub-questions* list inside the question modal (new — geo types included) and the existing
  "Add Sub-question" under the question in the section list. A geo question with no
  sub-questions stays valid; the modal only hints.
- **Answers about objects.** An answer may reference a layer object instead of carrying
  geometry: one answer per (session, sub-question, object); hidden/abandoned ones purged like
  other answers; export as a CSV keyed by object plus the layer GeoJSON enriched with
  per-object aggregates; per-object aggregates in Responses; public-results aggregates under
  the existing k-anonymity mask.
- **New input type `thumbs`** (👍/👎) in the *Questions* group, stored as `up`/`down`,
  aggregated as for/against.
- **Editor question modal**: *Sub-questions* list for geo and `layer_objects` types; picker
  gains the two types; "Objects on the map" form has layer picker, minimum-answered,
  auto search/chips toggle.
- **Survey settings → Reference layers card** gains "Open editor"; its Settings body stays.
- **ZIP export/import** carries object content and attachments; **duplication/versioning**
  copies objects with the layer.
- Not in scope (deferred, recorded in backlog on archive): variant B (card in the panel,
  also for geo sub-questions) as a creator-selectable alternative view; per-object styling;
  layer versioning; collaborative editing.

## Capabilities

### New Capabilities
- `layer-objects`: the object entity behind a reference layer — key, content fields,
  geometry, attachments (types, caps, storage tier, embed links), derived GeoJSON, delivery
  to the respondent page, migration of existing layers.
- `layer-object-editor`: the full-page object editor — list at scale, drawing/import entry
  points, card editor, bulk content and photo import, keyboard and bulk operations.
- `layer-objects-question`: the `layer_objects` question type on the respondent side — list
  block, search/chips, popup-as-card, answered state, counter and minimum, interaction rules
  with drawing.
- `object-answers`: answers that reference an object — model and uniqueness, persistence and
  purge, Responses aggregates, ZIP export shape, public-results masking.
- `thumbs-question`: the 👍/👎 input type — respondent widget, storage, export and aggregate.

### Modified Capabilities
- `reference-overlay-layers`: a layer's GeoJSON is derived from its objects; object popups
  render the object card; upload validation moves to "import into objects"; the ZIP delivery
  endpoint and per-section visibility are unchanged in behaviour.
- `survey-editor`: "Sub-question management for geo questions" widens to any question with
  objects on the map and gains the in-modal *Sub-questions* list; "Reference layers card"
  gains the Open editor entry.
- `question-type-picker`: two new types with icon, hint and group; the layout rule (map-only
  types hidden on form sections) applies to `layer_objects`.
- `survey-serialization`: `layers[]` carries objects with content and attachment manifests;
  archive gains `layers/<n>/assets/`; new question types and `object` answers round-trip.

## Impact

- **Models/migrations**: new `LayerObject`, `LayerObjectAsset`; `Answer.layer_object` FK +
  uniqueness; `Question` gains `layer` FK and `min_objects` for `layer_objects`; migration
  splits existing `SurveyMapLayer.geojson` into objects.
- **Backend**: `survey/layers.py` (derived GeoJSON, import/validation, CSV/photo matching),
  new `survey/layer_objects.py` editor views, `forms.py`/`widgets.py` (thumbs, layer_objects
  field), `views.py` (POST handling for object answers, purge), `analytics.py` (per-object
  aggregates), `public_results.py` (object blocks under k-anon), `serialization.py`,
  `cloning.py`, `versioning.py`, `question_types.py`, `html_sanitize.py` unchanged (reused).
- **Frontend**: new editor page + JS (list virtualisation, Leaflet.draw, autosave card,
  uploads); `base_survey_template.html` (list block, popup reuse, answered state);
  `question_form_modal.html` (Sub-questions list, layer_objects fields); picker; CSS.
- **Storage**: creator attachments on the public artwork tier with random keys
  (`media-storage` "Creator artwork is publicly readable"), sizes capped per file.
- **Specs**: 5 new, 4 deltas; `geo-multi-feature-input` deliberately untouched (D5).
- **Kill switch**: none new (owner rule); `MAP_REFERENCE_LAYERS` continues to gate layers and
  therefore everything built on them.
- **Risk**: the migration of existing layers and the `Answer` uniqueness constraint are the
  two irreversible steps; both ship in the first PR with a rehearsal against a prod dump.
