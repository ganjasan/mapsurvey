## Why

Respondents who agree with a mark someone else already placed have no way to say so: they
place a duplicate, and the creator de-duplicates by hand afterwards. Cllr Julian Thomas
(Whitehouse Community Council, dog-bin siting, 2026-09-03) named it unprompted — *"the
ability for respondents to see previous submissions and 'up vote' them instead of adding a
new pin would have been great"* — and it is the like/dislike every incumbent
(Ideenkarte, Maptionnaire, Open Point) ships. Backlog #160.

The merged `overlay-features` change (#155) already built the whole reaction machine for
the *creator's* objects: a reference layer of `LayerObject`s, an "Objects on the map"
question whose sub-questions (👍/👎, text, rating) are answered per object, per-object
results, export and a public block. What is missing is one more **source of objects**:
other respondents' marks. Nothing about the popup, the answers or the results changes.

## What Changes

- **A reference layer can be sourced from answers.** `SurveyMapLayer.source` ∈
  {`upload`, `question`}. A `question` layer names a geo question by code; its objects are
  materialised from that question's answers on every section submit (key stable per
  session + mark index, so a re-submit updates the object instead of recreating it and
  losing reactions). The object editor is read-only for such layers.
- **Per-layer visibility settings** (only meaningful for `question` layers): *show tallies*
  (default on), *show other people's comments* (default off), *approve marks before they
  appear* (default off).
- **Moderation.** `LayerObject.status` ∈ {`visible`, `pending`, `hidden`}; a new *Shared
  map* view on the Responses tab lists marks with Approve / Hide / Show; comments (text
  sub-answers) can be hidden one by one (`Answer.hidden`). Marks from sessions that are
  deleted, `not_approved` or `on_hold` never appear.
- **Own marks excluded.** The gated layer endpoint omits the requesting session's own
  objects for `question` layers and is no longer shared-cacheable for them.
- **Tallies and comments reach the respondent** through the existing surfaces: feature
  properties (list + map badges) and the object card endpoint (popup), gated by the two
  settings above.
- **Assembled by hand, on purpose.** The creator creates the layer in Survey settings
  ("New layer from answers", pick the geo question and the sub-question used as the label)
  and binds an "Objects on the map" question to it in any section, with whatever
  sub-questions they want (👍/👎, comment, rating). No wizard, no toggle on the geo
  question *(owner, 2026-09-05: "let them build a proper question and configure it as they
  like")*.
- **Export carries the verdict.** The geo question's own GeoJSON gains `mark_key`,
  `votes_up`, `votes_down`, `comments` properties, so ten residents asking for the same
  corner are one feature with 👍 9. The per-object CSV/GeoJSON from #155 works unchanged.
- **ZIP round-trip** carries the layer config (source code + settings) and the pair
  question; objects are not exported (they are answers).

Not in scope: a public comment feed with threading, reactions on the public results page,
respondent accounts, per-IP rate limiting beyond what the section POST already has.

## Capabilities

### New Capabilities
- `shared-map-layer`: a reference layer sourced from a geo question's answers —
  materialisation, stable keys, own-mark exclusion, clean-session filtering, tallies and
  comments delivery, caching rules, export properties, ZIP round-trip.
- `shared-map-moderation`: object status lifecycle (visible / pending / hidden),
  approve-first mode, per-object and per-comment hide, the Responses → Shared map view.

### Modified Capabilities
- `survey-editor`: the *Reference layers card* creates and configures `question` layers
  (source question, label sub-question, the three settings); deleting a source geo
  question is refused while a layer references it.
- `reference-overlay-layers`: the *gated cacheable endpoint* requirement gains the
  `question`-layer rules (session-varying response, no shared cache, own marks omitted).
- `survey-serialization`: *Reference layers serialization* carries `source`, the source
  question code and the three settings; `question` layers export no objects and import
  empty.

Prerequisite: `overlay-features` is merged but not yet archived. Its delta specs
(`layer-objects`, `layer-objects-question`, `object-answers`, `thumbs-question`) must be
synced into `openspec/specs/` before this change archives; this change builds on them and
does not restate them.

## Impact

- `survey/models.py`: `SurveyMapLayer` (+`source`, `source_question_code`,
  `show_tallies`, `show_comments`, `approve_first`), `LayerObject` (+`status`,
  `source_answer`, `source_session`), `Answer` (+`hidden`). One migration.
- `survey/layers.py`: materialisation (`sync_question_layer`), `build_layer_geojson`
  filtering by status/session, tally properties.
- `survey/views.py`: section POST hook after geo answers are saved; `survey_layer_geojson`
  and `survey_layer_object` for `question` layers; `download_data` properties.
- `survey/editor_views.py`, `editor_forms.py`, Survey settings layer card: source
  picker, settings, read-only object editor, refusal on delete.
- Responses tab: new *Shared map* pane (`object_stats.py` + a template); session
  validation-status changes trigger a layer rebuild.
- `survey/serialization.py`: layer config fields.
- Tests: `survey/tests.py` (materialisation, exclusion, moderation, endpoint caching,
  layer card, serialization); browser pass for the respondent flow.
- No new kill switch; `MAP_REFERENCE_LAYERS` still gates all of it.
