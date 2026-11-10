## 1. Types, settings and storage

- [x] 1.1 `question_types.py`: add `budget` (plain, `CHOICE_TYPES`); picker metadata (label, `fa-coins`, hint); `INPUT_TYPES` in `models.py`. No geo type (rework 2026-11-10)
- [x] 1.2 `normalise_budget_settings()` (mode/total/unit/symbol/step/rule/min_items/show_shares/source/cost_property; percent → total 100) and `format_amount()` in a new `survey/budget.py`
- [x] 1.3 `normalise_choice_extras`: `description` (≤ 300), `cost` (number ≥ 0), `max_count` (int ≥ 1) with caps in `CHOICE_EXTRA_LIMITS`
- [x] 1.4 Migration: `Answer.allocation` and `QuestionGroup.budget` JSONFields (nullable); `Question.budget_settings()` / `budget_items()` / `price()`, `QuestionGroup.budget_settings()`; `budget.normalise_price`, `measure`, `feature_cost`, `GroupSpend`
- [x] 1.5 `versioning.structural_question_changes`: mode/total/unit/step/source/cost_property, item cost/max_count, removed answered item → structural; the rest content

## 2. Editor

- [x] 2.1 `QuestionForm`: `vs_budget_*` fields, `clean()` (costs required for projects/items, step ≤ total, layer+cost_property for source layer, one layer owner per section), `budget_items` only on map sections (`MAPLESS_LAYOUTS` rule)
- [x] 2.2 `services/questions.py`: settings normalisation, `budget_map` gate (`trial.may` / `trial.use` once per created question), layer binding (PROTECT path shared with `layer_objects`)
- [x] 2.3 `question_form_modal.html` + JS: Budget block (mode cards, total/unit/symbol/step, rule, min items, show shares, source switch), choices table columns Description / Cost / Max count, layer + cost-property pickers (`property_names`), Pro badge, "N objects have no cost" notice
- [x] 2.4 Picker: `budget` after `ranking`; live preview renders the respondent block; group dialog Budget block (total/unit/symbol, Pro badge, unpriced-members warning); Price block (amount, per) in the geo question dialog inside a budget group
- [x] 2.5 Translation table: occurrence `question:<code>:choice:<code>:description`; read-only mirror in the choices table

## 3. Respondent

- [x] 3.1 `forms.py`: `BudgetField`/`BudgetWidget` (`budget.html`: sticky bar, Split steppers+slider / Projects cards, hidden inputs `budget__<code>`), `BudgetItemsField` rendering the palette block next to the point placement controls
- [x] 3.2 `js/budget_question.js`: remainder math, step rounding, disabled-with-reason, "spread the rest evenly", Next hint under `rule == 'all'`, phone (no slider, `inputmode=numeric`)
- [x] 3.3 Budget group on the respondent page: bar in the group header, price caption + `data-price-*` on the draw buttons, `refreshGroups` from `refreshGeoQuestionUI` (disable a per-mark button that no longer fits), `admit` from `draw:created` (refuse a line/area that costs more than what is left), recompute after edit (no new placement path — helper-count test unchanged)
- [x] 3.4 `save_section_answers`: `budget` → one row with `allocation` (store nothing for non-step / over / under-`all`); `_enforce_group_budgets` admits a budget group's marks in stored order and drops what does not fit
- [x] 3.5 Layer-sourced items: layer placed on the section map (`layers.py`), panel list rows open the object popup with the pick/allocate control; refuse two questions bound to one layer on one section
- [x] 3.6 Respondent strings in all respondent catalogs; creator strings in all creator catalogs

## 4. Results, export, print

- [x] 4.1 `survey/budget_stats.py`: split / projects (`fits`) / items aggregates over clean sessions, shares against the stored total
- [x] 4.2 Responses overview block (`analytics.py` + template) per mode; one `budget_group` block before a budget group's first member
- [x] 4.3 Public results: block kind `budget` (`public_results.py`, editor block form, template), k-anonymity per item, item-name-only labels on the geo display
- [x] 4.4 `export.py`: per-item columns + total for `budget`; `cost` property on priced marks and a `<group>: spent` column per budget group
- [x] 4.5 `survey/print/`: shapes for Split (table + Total), Projects (checkboxes + cost + Total); budget note under a budget group's heading, price line under a priced mark; strings from respondent catalogs

## 5. Serialization, API, MCP

- [x] 5.1 `serialization.py`: export/import of budget settings, item extras, layer binding by name with list fallback + report line; responses import of `allocation` and item codes
- [x] 5.2 `api/v1/schemas.py` + `forms_bridge.py` + `structure.py`: `budget` and `price` on questions, `budget` on groups; regenerate `reference/api.md` and `reference/mcp-tools.md`
- [x] 5.3 `billing/features.py`: `budget_map` Pro feature + `TRIAL_ALLOWANCES` entry; billing tests

## 6. Tests and docs

- [x] 6.1 `survey/tests/test_budget_question.py` (new module ↔ spec): settings normalisation, extras caps, storage shapes, refusals (over/under/step/unknown/max_count), layer source costs, round-trip, structural-vs-content, Pro gate, aggregates (`fits`, stored-total shares), placement path count unchanged
- [x] 6.2 Additions in `test_response_data_export`, `test_survey_serialization`, `test_public_results_page`, `test_printable_form`, `test_question_type_picker`, `billing/tests/test_plan_entitlements`
- [x] 6.3 Full suite `./run_tests.sh survey billing api mcp newsletter`; deprecation gate unchanged
- [x] 6.4 Help centre `how-to/budget-questions.md` + `help_links.py` key; What's new entry `survey/changelog/<date>-budget-questions.html`; CLAUDE.md paragraph "Budget questions"
- [x] 6.5 Verify on the dev stand (`/verify`): Immingham-style Split, Projects, a budget group over a park's benches / lamps / paths / beds; Responses and public results blocks
