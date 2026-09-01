## Context

FD-1 (`reference-overlay-layers`) stores a reference layer as one re-serialized GeoJSON
string on `SurveyMapLayer.geojson` (≤10 MB, ≤5000 features, ≤10 layers per survey), styled
as a whole, served to respondents through a gated `survey_layer_geojson` endpoint with an
ETag, rendered in a dedicated Leaflet pane with `interactive: false` unless `show_popups`.
`key_field` exists and has no consumer. Layers hang off `SurveyHeader` and are **not**
copied by `clone_survey_for_draft` (`versioning.py:246`) — a draft copy of a published
survey today has no layers and its `hidden_layers` IDs point at the canonical's rows. That
gap has not bitten because layers shipped a week ago and nobody has versioned a survey with
one yet; it becomes structural once answers reference objects.

Sub-questions of geo questions (`parent_question_id`) are the only existing "ask about an
object on the map" mechanism: the respondent's placed feature opens a Leaflet popup built by
`_buildPopupHtml` in `base_survey_template.html` with the sub-question form and ✓ / ✎ / 🗑;
answers are created under `parent_answer_id` on the geo answer. `geo-multi-feature-input`
fixes that placed features are managed on the map, never in a panel list.

Creator artwork (`Question.image`, `cover_image`, thanks-page images via
`editor_survey_thanks_image`) lives on the public S3 tier (`PublicMediaStorage`);
respondent uploads (`Upload`) on the private tier with signed URLs, 25 MB per file, MIME
sniffed in `survey/uploads.py`. Quill is the rich-text editor everywhere; `coerce_creator_html`
allows `img`, `iframe`, `a`.

Requirements, personas, journeys, decisions D1–D9 and the approved mockups are in
`user-stories.md`, `mechanism-ab.mockup.html` (section 0 + A), `layer-editor.mockup.html`,
`respondent.mockup.html` (list block only), `editor.mockup.html` (sections 1, 3).

## Goals / Non-Goals

**Goals:**

- A creator with no GIS and no hosting can put objects with photos and text on the map and
  ask about each one; a creator with 300 objects can manage them in an afternoon.
- One sub-question mechanism for geo questions and layer objects; respondent-side reuse of
  the existing popup so the geo flow and its spec stay untouched (D5).
- Answers about objects are first-class: unique per (session, sub-question, object), purged
  like any other answer, exported keyed by object, aggregated per object under k-anonymity.
- Existing FD-1 layers migrate losslessly; the gated GeoJSON endpoint, per-section
  visibility and the kill switch keep their contracts.

**Non-Goals:**

- Variant B (object card in the panel; geo popups moving to the panel) — later, as an
  alternative view (D6).
- Per-object styling in the editor (simplestyle from imported files is still honoured).
- Layer versioning, collaborative editing, offline editing.
- Changing the respondent panel layout on mobile (owner-kept legacy panel).

## Decisions

### D-1 Objects are rows; GeoJSON is derived

`LayerObject(layer FK, key, title, category, description, link, geometry, position,
properties JSON, created/updated)` with `unique(layer, key)`. Geometry is a GeoDjango
`GeometryField` (point/line/polygon, SRID 4326) — one column, one index, no per-type
columns. `properties` keeps the imported feature's raw properties (simplestyle included)
so nothing from a GIS file is thrown away.

`SurveyMapLayer.geojson` becomes a **cache**: rebuilt from objects on every object write
(debounced per request), still served by the existing endpoint, `updated_at` still drives
the ETag. Feature properties in the derived GeoJSON = raw `properties` + reserved
`_key`, `_title`, `_category`, `_has_content`, `_cover` (thumbnail URL) — enough for the
respondent list and popup without a second fetch; description and attachments are fetched
per object on popup open (`GET /surveys/<uuid>/layers/<id>/objects/<key>/`, same gate as
the layer endpoint) so a 300-object layer does not ship 300 rich-text bodies up front.

*Alternative rejected*: keep GeoJSON as source and put content in properties (the 1b
mockup). Hundreds of objects with attachments, uniqueness of keys, per-object endpoints and
answer FKs all want a row; parsing a 10 MB string to edit one title does not scale.

### D-2 Attachments are a table on the public tier, with random keys

`LayerObjectAsset(object FK, kind ∈ {image, audio, document, video, embed}, file
(PublicMediaStorage, path `layer_assets/<uuid4>.<ext>`), embed_url, title, size_bytes,
position)`. Caps: 25 MB per file (same constant as respondent uploads), 10 assets per object,
200 MB per layer; MIME sniffing reused from `survey/uploads.py`. `video` accepts an uploaded
file under the same cap; larger video goes in as `embed` (YouTube/Vimeo URL → sanitized
iframe; the sanitizer already allows `iframe`, we restrict `src` hosts to the two).

Public tier because respondents load these unauthenticated on `/surveys/` pages and
`<img>`/`<audio>` cannot carry signed headers; random keys are the same exposure model as
`Question.image` today (`media-storage` "Creator artwork is publicly readable"). Draft-survey
content is therefore reachable by anyone holding a URL — accepted, documented in the spec.

The first `image` asset by position is the **cover** (list thumbnail, popup header).

### D-3 Layers and objects are owned by the canonical survey; versions borrow them

A new helper `layers_for(survey)` resolves `survey.canonical_survey or survey` and every
reader (`build_map_layers_metadata`, `_editor_layers`, the geojson endpoint, the object
editor, serialization of versions) goes through it. `clone_survey_for_draft` keeps *not*
copying layers, now on purpose: a draft copy edits the same objects. `Question.layer`
(new FK for `layer_objects` questions) therefore survives cloning unchanged.

Consequences, accepted: (a) object edits on a published survey are **live** for respondents
— the editor shows a "published: changes are visible immediately" banner and asks before
deleting an object that already has answers; (b) `Answer.layer_object` stays valid across
versions, which is exactly what cross-version aggregates need; (c) discarding a draft copy
does not roll back object edits — the copy never owned them.

*Alternative rejected*: copy objects + assets into every draft and merge back on publish.
Hundreds of objects, S3 copies, and a merge step for a feature that has no merge semantics.

### D-4 Migration of FD-1 layers is a data migration, feature-by-feature

For each existing layer: parse `geojson`, create one `LayerObject` per feature — `key` =
`properties[key_field]` if set and unique in the file, else `f-<index>`; `title` =
`properties[label_field]` or `properties.name` or the key; `properties` = raw; geometry
from the feature (GeometryCollection / Multi* are exploded into one object per part with
`key-<n>`). Then rebuild the derived GeoJSON and compare feature counts and a bbox to the
original; mismatches log and keep the original string in `geojson_legacy` for one release.
`label_field`/`key_field` stay on the layer as *import mapping defaults*.

### D-5 `layer_objects` is a question type; sub-questions hang off it

`Question.input_type = 'layer_objects'` (label "Objects on the map", `fa-map-marked-alt`,
group *Map questions*; hidden on form-layout sections like the geo types). New fields on
`Question`: `layer` (FK, nullable, PROTECT), `min_objects` (int, default 0),
`objects_search` (`auto`/`on`/`off`, default `auto`: shown when a category exists or count >
5). Sub-questions use `parent_question_id` exactly as geo questions do; the sub-question
form excludes geo types and `layer_objects` itself.

The editor's question modal grows a *Sub-questions* section for `point/line/polygon/
layer_objects`: a nested list rendered from the same `question_list_item.html` partial in
"sub" mode and an "Add sub-question" button posting to the existing
`editor_subquestion_create` — the list is a second view onto the same data as the section
list; no new create path.

### D-6 Answers reference objects through a nullable FK, one row per sub-question

`Answer.layer_object` (FK, nullable, CASCADE) + `UniqueConstraint(survey_session, question,
layer_object)` where `layer_object IS NOT NULL`. A respondent's answers to a
`layer_objects` question are the sub-question `Answer` rows carrying `layer_object`; the
parent `layer_objects` question itself stores no row (like `html`). `parent_answer_id` is
**not** used — #152's constraint: the creator made the object, not the respondent.

POST handling: the popup form posts through the existing section POST with field names
`obj__<key>__<subq_code>`; the visibility engine treats sub-questions of a hidden
`layer_objects` question as hidden (existing rule); `min_objects` is validated as "distinct
`layer_object` with ≥1 non-empty sub-answer ≥ min" and reported with the existing
required-inline message. Section navigation purges answers for objects no longer in the
layer (deleted object ⇒ CASCADE anyway).

### D-7 Respondent rendering reuses the geo popup verbatim (variant A)

The list block renders from the derived GeoJSON already loaded for the layer (no second
fetch for the list); rows carry `_key`/`_title`/`_category`/`_cover`. Clicking a row or a
feature: `map.flyToBounds`, highlight class on the feature, then `layer.openPopup()` with
`_buildPopupHtml(formId, cardHtml + sqHtml)` where `cardHtml` is fetched from the object
endpoint (cached per key) and `sqHtml` is the pre-rendered sub-question form from
`window._subquestionsForms[questionCode]` — the same source geo questions use. Controls:
only `layer-apply` (✓); `onPopupClose` keeps typed values exactly as for geo. Answered
state: a Set of keys with any non-empty value drives ✓ on rows, the `answered` feature
class and the counter.

Interaction guard: while a draw handler is active (`drawControl` active or crosshair mode)
object features get `interactive:false`, restored on `draw:drawstop` — the FD-1 guarantee
and C5.

`show_popups` on the layer keeps its meaning for layers **not** bound to a `layer_objects`
question (read-only name/description); a bound layer's popup is the object card.

### D-8 `thumbs` is an input type over a fixed two-choice list

`input_type = 'thumbs'`, stored like every choice type — `Answer.selected_choices` holding
code `1` (up) or `0` (down) — with `Question.choices` pinned to `THUMBS_CHOICES`
(`[{1: "up"}, {0: "down"}]`) by the editor and never shown in the choices editor.
*Revised during implementation* from "store `up`/`down` in `Answer.text`": storage,
export, analytics, visibility rules, public-results charts and serialization all branch on
the choice-type tuples, so a choice-shaped thumbs gets every consumer for free — export
cells read `up`/`down` through the choice names, aggregates are the two counts, and a
thumbs question can drive a visibility rule like any choice. Widget = two large buttons
over a radio pair (`thumbs.html`), labels localised in the template. Picker group
*Questions*, icon `fa-thumbs-up`.

### D-9 Editor screen is a Django page with one page-level JS module

`/editor/surveys/<uuid>/layers/<id>/` (owner only; 404 under the kill switch) renders the
three-column page from `editor_base.html`. Data: initial object list as JSON
(`key,title,category,cover,asset_counts,has_text,geometry_type,bbox`) — 300 objects ≈ 60 KB
— rendered by a small virtualised list (no framework; the page is desktop-first, mobile gets
the list and card stacked). Endpoints (JSON, CSRF, owner-gated):

- `POST objects/` create (from drawn geometry) · `PATCH objects/<key>/` autosave fields ·
  `DELETE objects/<key>/` · `POST objects/<key>/geometry/`
- `POST objects/<key>/assets/` (multipart) · `PATCH/DELETE assets/<id>/` · `POST assets/reorder/`
- `POST import/geojson/` (mapping in the body, dry-run flag returns a report) ·
  `POST import/csv/` (coordinates or content, matched by key then title) ·
  `POST import/photos/` (multiple files matched by filename stem to key then title)
- `POST bulk/` (`set_category`, `delete` over a key list)

Leaflet.draw and the FontAwesome marker icon are the respondent's; the map shows the layer's
derived GeoJSON and follows list selection. Autosave = debounced PATCH with the same
saved/saving/error indicator pattern as `EDITOR_AUTOSAVE`.

### D-10 Export and aggregates

`download_data` ZIP gains, per `layer_objects` question, `objects_<code>.csv` (session_id,
object_key, object_title, sub-question columns) and per bound layer
`layers/<name>.results.geojson` (derived GeoJSON + `answers`, per-sub-question aggregates:
`mean`/`count` for rating, `up`/`down` for thumbs, distribution for choice, count for text).
Responses tab: the layer's map badge and a per-object table reuse `SelectionManager` on
`object_key`. Public results: a new block type `object_ratings` (bar per object) computed by
`PublicResultsService` with the page's `k` — objects with `< k` answers masked, text never
published (E3).

### D-11 Serialization

`layers[]` entries gain `objects/<n>.json` (fields + raw properties + asset manifest) and
`layers/<n>/assets/<uuid>.<ext>`; geometry travels inside the existing
`layers/<n>.geojson` (derived) keyed by `_key`. Import recreates objects then assets (files
copied into storage, missing files ⇒ warning per asset, never a hard error). Questions of
type `layer_objects` reference their layer by position index like `hidden_layers` does;
`thumbs` needs no special handling. AI generation cannot produce layers (unchanged).

## Risks / Trade-offs

- **Migration splits production layers** → rehearse on a prod dump; keep `geojson_legacy`
  one release; the derived GeoJSON must byte-equal in feature count and bbox before the
  legacy column is dropped.
- **Live edits on published surveys (D-3)** → banner + confirm on delete-with-answers;
  documented in the spec; owner accepted the trade-off over draft/merge complexity.
- **Public-tier assets leak draft content by URL** → random UUID keys; same as existing
  creator artwork; called out in `layer-objects` spec.
- **Popup with cover + text + 3 sub-questions is tall on phones** → popup already sized to
  90 % × 70 % of the viewport with internal scroll (`_subquestionPopupOptions`); cover
  capped at 160 px inside popups; owner chose A knowing this, B is the escape hatch.
- **300 objects × labels on the map** → labels only above a zoom threshold for layers with
  > 50 objects; list is virtualised; derived GeoJSON stays under the 10 MB cap (enforced on
  object create with a human-readable error).
- **`Answer` uniqueness constraint fails on existing data** → constraint is partial
  (`layer_object IS NOT NULL`); existing rows have NULL.
- **Sub-question modal list duplicates the section list** → both render the same partial;
  HTMX swaps after create/delete target both via `hx-swap-oob`.
- **Quill in a card that autosaves per field** → description saves on blur/debounce like
  the thanks page; image button reuses `editor_survey_thanks_image`'s upload contract via a
  layer-scoped endpoint.

## Migration Plan

1. PR 1 — *Objects editor* (slice 1): models, migration (objects split + `geojson_legacy`),
   derived GeoJSON, editor screen, imports, assets, serialization/versioning helpers, "Open
   editor" button. Respondent side unchanged except popups on bound layers (none yet).
   Pre-deploy migration is data-heavy but idempotent; rollback = revert code, columns stay.
2. PR 2 — *Browse + Answer* (slices 1b, 2): `layer_objects` and `thumbs` types, in-modal
   sub-questions, respondent list block + popup, `Answer.layer_object`, POST/purge/minimum.
3. PR 3 — *Read* (slice 3): export CSV + results GeoJSON, Responses aggregates, public
   results block; drop `geojson_legacy`.

No kill switch (owner rule); `MAP_REFERENCE_LAYERS=False` still hides every surface.

## Follow-ups noticed during implementation

- The public `objects` block lists every object of the layer; on a 221-object layer with
  one answered object that is 220 rows of zeros. Cap or "answered first, fold the rest"
  before a real municipality publishes one.
- The rating sub-question inside the object popup renders as plain radios (the popup uses
  `as_p()`, exactly like geo popups do); the stars style does not reach popups. Same gap
  as today's geo sub-questions — fix once, for both.
- The Responses per-object table has no filter; 200+ rows scroll. Search/category chips
  like the editor's list would be the natural next step.

## Open Questions

- Category as free text with autocomplete (mockup) vs. a per-layer category list with
  colours — free text in PR 1; colours per category are a natural follow-up once
  per-object styling is wanted.
- Whether the Responses tab's per-object table lands in PR 2 (with the answers) or PR 3
  (with the aggregates) — proposal says PR 3; move earlier if Sarasota needs to read
  results before export exists.
