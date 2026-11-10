## Context

Issue #447 asks for budget questions; the journey mockup in this folder (`journey.mockup.html`)
fixes the three modes and the screens. The closest existing type is `ranking` (a `CHOICE_TYPES`
member, items in `choices`, one `Answer` row per respondent, one export column per item); the
closest map precedents are `point` (placement through the crosshair / `tap_to_place` helpers,
`geo_answer_features` as the one builder of the restored feature shape) and `layer_objects`
(`Question.layer`, PROTECT; the panel list as navigation into the same Leaflet popup).

Constraints that shape the design: every geo consumer dispatches on `input_type in GEO_TYPES`
and `geo_column()`; `normalise_choice_extras` is the one place choice extras are capped; the
service layer validates by binding `QuestionForm`; Pro is a registry row gated by
`trial.may/use`; `test_placement_paths_go_through_one_helper` counts placement paths; one test
module per spec.

## Goals / Non-Goals

**Goals:**
- Three modes, one creator vocabulary ("Budget"), one respondent idiom (a sticky budget bar with
  the remainder as the primary signal).
- Items from a list or from a layer's objects without copying anything.
- Results on every read surface from one aggregate; export a clerk can pivot.
- Everything a question type must do today: ZIP, API/MCP, translations, live-editing rules,
  printable form, editor preview.

**Non-Goals:**
- The tax / precept trade-off simulator (candidate 3 in #447) — a matrix with a formula, its own issue.
- Reading budget answers off paper photos (paper-photo-entry extraction) — the printed shape only.
- Per-item caps in Split (`max_per_item`), weighted costs by object size, comments per allocation.
- Rewriting `/participatory-budgeting/` — copy follow-up.

## Decisions

**D1. Two stored input types behind one creator-facing family.** `budget` (Split / Projects) is a
plain `CHOICE_TYPES` member; `budget_items` (Place items) is in `GEO_TYPES` with
`geo_column('budget_items') == 'point'`. *Why not one type with three modes:* every geo consumer
(`save_section_answers`, `analytics`, `public_results`, `export`, print, Map pane, cluster map,
spray/coverage exclusions) tests `input_type in GEO_TYPES`; a plain type with a geo mode would
need a mode check beside each of them, and the section-layout rule (`MAPLESS_LAYOUTS` excludes
geo questions) would have to look inside settings. The picker names them "Budget" (Questions
group) and "Budget: place items on the map" (Map questions group). `budget_items` joins
`PARENT_TYPES` automatically (sub-questions per placed item) and stays OUT of
`MULTI_FEATURE_TYPES` (the budget is the cap, not min/max features) and `SHARED_MAP_SOURCE_TYPES`.

**D2. Settings live in `validation_settings['budget']`**, not new columns:
`{"mode": "split"|"projects", "total": number, "unit": "currency"|"points"|"percent",
"symbol": str ≤ 4, "step": number, "rule": "all"|"upto", "min_items": int, "show_shares": bool,
"source": "list"|"layer", "cost_property": str}`. For `budget_items`: `total`, `unit`, `symbol`,
`min_items`. `unit == "percent"` fixes `total = 100` and no symbol. The editor dialect is
`vs_budget_<key>` fields on `QuestionForm`, which is what the service and `forms_bridge` already
speak; `normalise_budget_settings()` in `question_types.py` is the ONE validator (form, import,
API). Rationale: `validation_settings` already carries per-type settings (`max_features`,
`max_dots`), rides the ZIP and the draft copy via `plain_field_values`, and needs no migration.

**D3. Items are `choices` with three new extras** — `description` (≤ 300 chars, plain text),
`cost` (number ≥ 0), `max_count` (int ≥ 1, `budget_items` only) — capped in
`normalise_choice_extras` next to `icon`/`group`/`color`, so every save path and the import get
them for free and every other consumer ignores them. Item names translate through the existing
`question:<code>:choice:<code>` occurrence; `description` gets a sibling occurrence key
`question:<code>:choice:<code>:description` in `translation_table.occurrences()`.

**D4. Layer-sourced items reuse `Question.layer`.** With `source == "layer"`, `choices` is empty
and the items are `layer.objects` (`layer_lite`, never the geojson text); the cost is
`properties[cost_property]` coerced to a number, an object without one is listed as not
selectable. Keys are object keys. The question puts the layer on the section map the way
`layer_objects` does (respondent card from `survey_layer_object` in the same popup). The layer
is owned by the canonical survey and nothing is copied: an object's cost edit is live for new
respondents, and the answer snapshots the cost (D5). `Question.layer` PROTECT already refuses
deleting a bound layer.

**D5. One answer shape for `budget`:** new `Answer.allocation` JSONField —
`{"total": 20000000, "items": {"<code>": <amount>}}`. In Split the amount is what the respondent
gave the item; in Projects the keys are the picked items and the value is the cost at answer
time. `spent = sum(items.values())`. `selected_choices` is NOT set: the choice consumers
(visibility controllers, choice charts, `get_selected_choice_names`) must not pick a budget up
by accident; `budget` is in `CHOICE_TYPES` only so that the choices table, translations,
`thumbs`-style guards and import treat its `choices` as meaningful. Storing `total` on the row is
what lets shares be computed after the creator changes the total on a new version.

**D6. `budget_items` rows are plain point answers with `selected_choices = [<item code>]`.** The
browser posts the existing GeoJSON `feature|feature` dialect with `properties.item = <code>`;
`save_section_answers` stores one row per feature with the item code in `selected_choices` and
the sub-answers as children, and `geo_answer_features` adds `item` back into properties. Cost is
not stored per row: it is the catalogue's cost at read time (the catalogue is structure, a cost
change is structural → Unpublished changes, D9). Validation at POST: unknown item → feature
dropped; `sum(cost) > total` or a type over `max_count` → the section re-renders with a field
error naming the overrun (not silent truncation: which feature to drop is the respondent's call).

**D7. Placement reuses the point path.** The palette (`partials/budget_items_block.html`) is a
list of radio tiles; choosing one sets the active catalogue item (icon + color through
`MarkerIcon.element`) and then the EXISTING draw button / crosshair / `tap_to_place` path places
the mark — no new placement path (the helper-count test stays at its number). The chosen tile
stays active after a placement so seven trees go down in a row. The popup is the point popup
with the item's name and cost in its header, Move/Remove, and the sub-questions. The budget bar
(`js/budget_question.js`) listens to the geo shell's feature add/remove events and recomputes
`spent`; a tile whose cost exceeds the remainder (or whose `max_count` is reached) is disabled
with the reason.

**D8. One aggregate module, `survey/budget_stats.py`**, over clean sessions, keyed by question:
Split → per item `mean_share`, `mean_amount`, `median_amount`, `zero_share`, `n`; Projects → per
item `pick_share`, `n`, plus `fits` = items by descending support while their costs fit `total`;
Place items → per type `mean_count`, `total_count`, `budget_share`, `n`, plus the points (the
Map pane and cluster map read them as any point question). `analytics.py` (Responses overview
block), `public_results.py` (block kind `budget`, masks an item with fewer than K non-zero / picked
/ placed respondents, like a choice bucket) and `export.py` all call it; no surface computes its
own.

**D9. Live-editing rule.** Changing `mode`, `total`, `unit`, `step`, `source`, `cost_property`, an
item's `cost` or `max_count`, or removing an item with answers is STRUCTURAL
(`versioning.structural_question_changes`); `rule`, `min_items`, `show_shares`, `symbol`, names,
descriptions, icons are content. Changing a layer object's cost is a layer edit — live, as all
layer edits are, and the object editor's banner already says so.

**D10. Pro gate = registry row `budget_map`** (`billing/features.py`, Pro plan; trial allowance
`None` = uncapped, counted). Checked where a map-bound budget is SAVED — `services.questions`
when `input_type == 'budget_items'` or `source == 'layer'` — through `trial.may(org,
'budget_map')`; the use is counted once per question created (`trial.use`). A published survey
keeps working after a lapse (the sites rule), so respondents never meet the gate. The picker
shows `{% pro_badge org "budget_map" %}` on the gated entries. If the owner decides "all free",
the row moves to every plan — nothing else changes.

**D11. Export.** Flat table: Split `"<question>: <item> (<symbol>)"` = amount, Projects
`"<question>: <item>"` = 1/0, Place items `"<question>: <item>"` = count; each followed by
`"<question>: total"`. GeoJSON/GPKG/SHP/KML: `budget_items` is a point layer with `item`,
`item_name`, `cost` properties, and the observations table gets them as columns, through the
existing `GeoLayer` collector (`geo_column` = point).

**D12. Printable form.** `budget` Split: a table "item · ______ <symbol>" with a Total row;
Projects: checkbox per item with the cost and a Total row; `budget_items`: the map frame with the
catalogue as its legend letters and a marks table with an "Item" column, through
`QUESTION_SHAPES`. `LAYOUT_VERSION` is unchanged (no chrome change). Photo extraction: out of scope,
the shapes are planned so `plan_items` lists them.

**Alternatives considered.** (a) Reuse `multichoice` + `cost` extras for Projects: no budget bar,
no refusal, and a cost on a choice would leak into every choice consumer. (b) Store Split in
`selected_choices` as `[[code, amount]]`: breaks `get_selected_choice_names` and the visibility
engine's `in selected_choices` checks. (c) Make Place items a `point` display style: the palette,
the budget refusal and the per-type aggregate are behaviour, not a look; `DISPLAY_STYLES_BY_TYPE`
is for looks. (d) Store the cost per placed row: a structural change would then show old and new
costs side by side on one version; the catalogue is structure, versions already separate it.

## Risks / Trade-offs

- [Slider arithmetic on a phone] → no slider below 769 px, steppers 40 px, tap-to-type with
  `inputmode=numeric`, rounding to the step; "Spread the rest evenly" for the `all` rule.
- [Respondent games the client] → the server recomputes `spent`, rejects over-budget, non-step
  and unknown items, and re-renders with the reason; `--parallel`-safe because nothing is cached.
- [Large totals read badly (20000000)] → `budget.format_amount()` renders £20M / £0.5M / 20 000;
  one function for respondent, Responses, export headers.
- [Layer source and `layer_objects` on the same section both place the layer] → `layers.py`
  lists a layer once per section; the budget question's panel list owns the popup action for its
  objects, `layer_objects` keeps its own; two questions bound to one layer on one section are
  refused by the form (one owner of the popup per layer per section).
- [`budget_items` in `GEO_TYPES` reaches consumers that assume four types] → the
  `LayerMemoryDietTest`/export/print suites run on the new type; `geo_column` is the seam; the
  spray exceptions (`MULTI_FEATURE_TYPES`, `SHARED_MAP_SOURCE_TYPES`) are explicit tuples and
  exclude it.
- [Pro decision pending] → a registry row; the proposal says what is gated, the owner flips it.
- [k-anonymity on Split] → an item with fewer than K respondents giving it a non-zero amount is
  masked exactly like a small choice bucket; the mean over the rest is still published.

## Migration Plan

1. Migration adds `Answer.allocation` (nullable JSON) — additive, no backfill, no lock on the big
   tables beyond `ALTER TABLE ADD COLUMN NULL`.
2. Deploy; the picker shows the types immediately. No kill switch (owner rule: no kill switches).
3. Rollback = revert the deploy; stored `allocation` rows are inert for older code (unknown type
   → the export's "unrecognised type" column, by spec).

## Rework after the first dev-stand review (2026-11-10)

The first build made "place items on the map" a fifth geo type (`budget_items`) with a palette of
priced tiles over one point button. The owner rejected it: *"Я хочу сохранить актуальное
поведение Geo вопросов, но просто добавить каждому объекту цену"* — and suggested the budget be a
kind of group. So D1, D6, D7, D8, D11, D12 are superseded by:

- **D1′. One question type, `budget`.** No geo type was added; `GEO_TYPES` is unchanged.
- **D6′. A budget is a GROUP setting** — `QuestionGroup.budget = {total, unit, symbol}` through the
  same validator (`normalise_budget_settings(…, 'group')`). Groups already give a container with a
  header, a visibility rule, ordered members, copying and the ZIP, and a section may hold two
  budgets. Set in the group dialog (empty total = ordinary group) and through the API.
- **D7′. A price is a GEO QUESTION setting** — `validation_settings['price'] = {amount, per}`, `per`
  ∈ `feature | length | area` narrowed by type (`PERS_BY_TYPE`), offered in the question dialog only
  inside a budget group. The draw button carries `data-price-*` and a caption ("£50 / m"). The geo
  question keeps everything else: sub-questions, min/max, tap-to-place, restore, export, paper.
- **Cost of a mark** = `budget.feature_cost(price, geometry)`: amount × 1 / metres / m², measured in
  Web Mercator corrected by cos(lat) / cos²(lat) the way `spray.cloud_area_m2` is; the browser
  mirrors it with `distanceTo` and `L.GeometryUtil.geodesicArea`.
- **Respondent**: the group header renders the bar (`[data-budget-group]`); `budget_question.js`
  sums the page's own `editableLayers` per member (`refreshGroups`, from `refreshGeoQuestionUI`),
  disables a per-mark button whose next mark could not fit, and refuses a drawn line/area that
  costs more than what is left (`admit`, from `draw:created`). No new placement path.
- **Server**: `views._enforce_group_budgets` admits the group's stored marks in id order with
  `budget.GroupSpend` and deletes the rest — the `max_features` clamp pattern.
- **Results**: `budget_stats.group_aggregate` (count / metres / m², cost, share of spend per
  member); Responses inserts one `budget_group` block before the group's first member. Export: a
  `cost` property per priced mark and a `<group>: spent` column per session. Paper: a budget note
  under the group heading and "Price: …" under a priced mark. Public results: the members' marks
  publish as ordinary map blocks; a group block is a follow-up.
- **Pro**: budget groups are FREE on every plan (owner, 2026-11-10 — the map-side budget is the
  product's differentiator and should be in every council's hands). `budget_map` stays for a
  budget question whose items are a layer's objects only.
- **Structure**: a group's total/unit and a question's price are structural on a live survey.
- **Colours (owner, second review)**: the bar is stacked per item in the item's colour — the
  `color` choice extra the icon grid already has (the Icon and Colour columns show for budget
  items), a group member's `Question.color` — with a fixed palette for items without one;
  Responses and public-results rows reuse it; every item row shows its colour (left edge, icon
  tile, checkbox, slider), so the bar's segments can be read against the list.
- **Placing chip (owner, second review)**: the panel is hidden while placing, so
  `budget_question.js` shows a fixed chip over the draw bar (`#budget-draw-chip`) with the armed
  question, the running metres / m² and cost of the shape under the pointer (`draw:drawvertex` +
  `mousemove` → `BudgetQuestion.drawing`) and what is left after it.
- **Discoverability (owner, second review)**: creators look for budgets where the map questions
  are, so the "New question" picker offers a **Budget group** card in Map questions —
  `question_types.PICKER_ACTIONS`, a picker-only action that posts to the group endpoint with
  `budget=1` (starting total 10 000, the typed name as title) and opens the group dialog, which
  reads "Budget group" and carries its own tips. The model/picker parity test stays about input
  types. A budget group cannot live in a pop-up.

## Implementation notes (what changed against the plan)

- **No error render on the section POST.** D6 planned a re-render naming the overrun; the section
  POST has no error path for ANY type (the client blocks Next; `max_features` clamps, an invalid
  ranking stores nothing). Budget follows that convention: `budget.parse_submission` stores nothing
  for an impossible allocation, `budget.PlacedItems` drops what does not fit, and
  `BudgetQuestion.firstInvalid` (hooked into the page's Next validation) writes the reason under
  the block. Adding an error path to the respondent POST is a separate decision.
- **Split posts per-item inputs** named `<code>__<item>` (works without JavaScript); Projects posts
  checkboxes under the question's name. `budget_question.js` only enhances.
- **`budget_items` reuses the point button**: the palette sets the button's `data-icon`/`data-color`,
  the page's draw:created handler calls `BudgetQuestion.decorate` to stamp `properties.item`, and
  `refreshGeoQuestionUI` calls `BudgetQuestion.refreshPlaced`. No new placement path
  (`hidePanelForPlacement();` count unchanged). Tap-to-place is on whenever it is the only geo
  question (`tap_to_place_active`).
- **Layer-sourced items**: the layer joins the section map through `layers.section_layer_ids`;
  picking is in the panel list. A pick action inside the object popup is a follow-up.
- **Public results**: a server-rendered `budget` block for both types; placed points on the public
  map are a follow-up.
- **ZIP**: `validation_settings` was never exported for any type, so the record travels under the
  question's `budget` key; the layer by its `layers` position, like Objects on the map.
- **Paper**: `budget_items` prints a numbered catalogue under its geo note; legend letters per item
  (what paper-photo extraction reads) are a follow-up.
- **Translations**: item descriptions translate through `description_i18n` on the choice, written
  only by the Translations tab (`services.questions.set_choice_descriptions`).

## Open Questions

- Pro or free (D10) — owner. Recommendation: free for Split/Projects from a list, Pro for the two
  map-bound forms.
- Trial allowance for `budget_map`: uncapped-counted (as `operator_entry`) or 3 questions?
- Should `/participatory-budgeting/` and the market guide gain a "Budgeting" criterion in
  `vendors.py` in this change or the next (facts need sources and dates)?
