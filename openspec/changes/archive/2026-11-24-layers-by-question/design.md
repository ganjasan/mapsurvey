# Design: layers-by-question

## Context

Today three things decide what a respondent sees on a section's map:

1. `layers_for(survey)` — every layer of the layer owner (canonical survey; draft copies and
   versions borrow), rendered by `reference_layers.html` from `build_map_layers_metadata`.
2. `SurveySection.hidden_layers` — IDs the section form's checklist unticked, passed as
   `data-hidden-layers` and removed client-side.
3. `layer_objects` questions — a bound layer gets `bound: true` in the metadata (computed
   survey-wide, not per section), which makes features open the object popup; the question's
   `layer_objects_block.html` lists the objects in the panel.

`overlay-features` (#155) and `respondent-shared-map` (#160) are merged but not archived;
their delta specs define the `layer_objects` type, the panel list, the popup, `min_objects`
and the `question`-sourced layers.

## Goals / Non-Goals

**Goals**
- One mental model: *add a question → the layer is on this map*. The question's position in
  the section is where its panel line sits. *(owner, 2026-09-06)*
- A layer with nothing to ask is still a first-class map layer: legend line in the panel,
  clickable objects with their cards, toggle in the layers control.
- No visible change for respondents of existing surveys on deploy day.
- Delete every second source of truth (`hidden_layers`, `bound` computed survey-wide).

**Non-Goals**
- A separate "Map layer" display block (variant B, rejected: two types sharing one binding).
- Per-respondent layer preferences, layer ordering UI, or changes to the object editor.
- Touching the Responses map (aggregates every layer, non-interactive — unchanged).

## Decisions

### D1. Visibility = binding
`layers.section_layer_ids(section)` = the layer ids bound by the section's top-level
`layer_objects` questions, in `order_number`. The respondent shell still loads every layer
of the owner once (`build_map_layers_metadata(survey)` is unchanged — layers live across HTMX
section swaps on the persistent map), and each section partial now carries
`data-visible-layers` (the bound ids) instead of `data-hidden-layers`;
`applyRefLayerVisibility(visibleIds)` allows exactly those. Entries start `allowed: false`,
so a section with no Objects question shows no layer. The editor preview passes the same
list. `bound` in the metadata stays survey-wide: a layer that is on a section's map is,
by construction, bound there. Form-layout sections have no map and therefore no layers,
unchanged — a `layer_objects` question in a form section is refused by the form (already
the rule). The Responses map ignores the per-section list as before.

*Why not keep `hidden_layers` as an override?* Two switches for one bit is exactly the bug.

### D2. No sub-questions ⇒ display only
`Question.collects_objects` (property) = `input_type == 'layer_objects'` and it has at least
one sub-question. Everywhere the object machinery asks "does this count" — answered-state
counter, `min_objects` validation, progress, the "n / m answered" chip, per-object results
table, export `objects` sheet, public block eligibility — it reads that property. The editor
form hides `min_objects` until a sub-question exists and shows "Shows the layer; add a
sub-question to ask about each object" in its place. `min_objects` stored on a question that
later loses its last sub-question is ignored, not zeroed (adding the sub-question back
restores it).

### D3. `panel_mode` on `Question`
`CharField(choices=('list', 'legend'), default='list')`. Editor: radio "In the panel —
List objects / Legend line". `legend` renders one row from the same metadata the layers
control uses: swatch (or rule legend, collapsed), name, count, on/off toggle wired to the
layers control's checkbox for that layer. `list` = today's block untouched. Both modes open
the same popup on feature click. Default `list` for new questions because a creator who
just picked a layer usually wants to see it; migration writes `legend` because a checklist
tick never produced a list.

*Why explicit and not "no sub-questions ⇒ legend"?* A layer of eight parks with photos and
descriptions is worth browsing without a question; a layer of 300 lamp posts with a question
is not. The two axes are independent.

### D4. One layer once per section
`QuestionForm.clean_layer` rejects a layer already bound by another top-level
`layer_objects` question of the same section: "Already on this section's map as '<name>'".
Cloning within a survey (`cloning.py`) keeps bindings (the layer belongs to the same owner);
cross-survey paste drops the layer and the question arrives unbound with a badge, as it does
today.

### D5. Data migration, then column drop — two migrations, two deploys
`00xx_layer_questions_from_hidden_layers` (data): for each `SurveySection` with
`layout='map'`, owner = `layer_owner(section.survey_header)`, for each owner layer whose id
is not in `hidden_layers` and not bound by a top-level `layer_objects` question of this
section → create `Question(input_type='layer_objects', layer=layer, name=layer.name[:250],
code=<next free code>, panel_mode='legend', min_objects=0, order_number=<max+1>)`. Idempotent
(re-run creates nothing). Runs inside the migration, plain ORM through `apps.get_model`, so
`layer_owner` is re-implemented locally over the historical models. The follow-up migration
removing `hidden_layers` ships one release later, per the pre-deploy rule (the deploy that
adds a migration must not also depend on its result).

*Why questions per section and not per survey?* Question rows are per header (canonical,
each version, each draft copy); the migration walks headers, and a draft copy gets the same
questions its published sibling has, so publishing it changes nothing on the map.

### D6. Serialization
Export: the `hidden_layers` key is gone; questions already ride with their `layer` reference
(by index into the exported `layers` array). Import: an archive with `hidden_layers` on a
section runs the D5 conversion for that section after its questions are created
(`serialization.convert_hidden_layers(section, hidden_ids)`, shared with the migration's
logic via a pure function that takes the layer list and the bound set). Archives written
after this change have nothing to convert.

### D7. "Upload a new layer" from the question form
The layer picker in the Objects form gains a last option "Upload a new layer…" that opens the
existing Survey-settings upload flow in the settings modal and, on success, selects the new
layer in the picker. No new upload endpoint; the settings card stays the library.

### D7b. Objects settings block layout — direction A
Mockups in `mockups/` (canvas: three directions, owner picked **A** on 2026-09-07): one card,
one story. Header "Layer on this map" with a status pill that reads either "Shows only ·
collects nothing" or "Asks about each object" (from `collects_objects`); the layer picker
with an "Upload new…" link to Survey settings beside it; a segmented List/Legend control whose
help line changes with the choice; "Search and category chips" only while List is chosen;
"Minimum objects" only while the question collects; the shared-map settings as a divided
sub-section; and the sub-questions block joining the same card as "Ask about each object"
(`lo-card--tail`), so the whole type reads top to bottom as layer → panel → questions.

### D8. Editor list badge and preview
The section question list already shows the layer badge and count on `layer_objects` rows;
it adds a "legend" or "list" word. The editor preview passes its section to
`build_map_layers_metadata`, so it shows exactly the respondent's layers (spec
"The editor preview renders reference layers" holds by construction).

## Risks / Trade-offs

- **Migration volume**: one question per (section × visible layer). Production has few
  layers (feature shipped 2026-09-05); the migration is O(sections × layers), trivial.
- **Question codes**: generated codes must not collide with respondent-facing exports; reuse
  `Question.generate_code` (whatever `editor_question_create` uses) inside the migration by
  copying its rule, not importing it.
- **Progress semantics**: a `layer_objects` question with no sub-questions used to count as a
  question (answered when `min_objects` met, i.e. always). Progress denominators drop by one
  on affected surveys — visible only as a percentage on the respondent progress bar.
- **Archive dependency**: `overlay-features` and `respondent-shared-map` must be archived
  before this change's MODIFIED deltas can apply (OpenSpec archive trap: a MODIFIED header
  needs the requirement in the main spec).

## Migration Plan

1. Archive `overlay-features`, `respondent-shared-map` (sync deltas to main specs).
2. PR 1: `panel_mode` field, data migration, code reading bindings only, checklist removed,
   import conversion, tests. `hidden_layers` column stays, unread.
3. PR 2 (next release): migration dropping `hidden_layers`; delete the serializer's
   `hidden_layers` write path guard.
4. Rollback of PR 1 = revert; the converted questions remain as plain Objects questions,
   harmless under the old code (they render a list — the one visible artefact).

## Open Questions

- **Type name in the picker.** "Objects on the map" reads as "asks about objects". Candidates:
  keep and change the hint; rename to "Map layer". *(owner)*
- **Legend line for `question`-sourced ("Marks") layers**: count of others' marks is
  privacy-safe (tallies already show); confirm it may appear in the legend line.
