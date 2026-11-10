## Why

Budget consultations are the one thing a local authority asks residents every year — a town
council's precept consultation, a city's participatory budgeting round, a "£20M for our area"
fund — and Mapsurvey has no question for them. A creator approximates it with a `ranking`
(issue #447; the "How would you spend £20M across Immingham" draft on production is exactly
that: five investment areas ranked 1–5, and a separate text question for a project idea), which
neither enforces a budget nor shows the trade-off nor ties money to places on the map. We also
run a `/participatory-budgeting/` landing page while the product cannot do it. Maptionnaire sells
this as *Budgeting* and *Geobudgeting*; Commonplace and PublicInput have an allocation question.

## What Changes

- A **Budget** question family with three modes, every one of them "spend a fixed budget":
  - **Split a budget** — the respondent distributes the budget (money, points or per cent) across
    the creator's items, with steppers and sliders in the creator's step; results are the mean
    share and amount per item.
  - **Choose projects within a budget** — each item has a cost; the respondent picks items until
    the budget is spent (an item dearer than the remainder is visible but cannot be taken);
    results are the share of respondents per project and the set that fits the budget.
  - **A budget on a question group** — the ordinary map questions inside the group each carry a
    price (per mark, per metre of a line, per square metre of an area) and the respondent places
    marks until the group's total is spent; the geo questions keep every behaviour they have
    (sub-questions, min/max, tap-to-place, export, paper), the budget only bounds how much goes
    down. Results: per member the marks, metres or m², their cost and the share of the spend.
- Split and Projects take their items either from a **typed list** (the choices table with new
  `description` and `cost` columns) or from the **objects of a reference layer** (cost read from
  an object property), so money can be attached to places the creator already mapped.
- Stored as ONE input type, `budget` (Split / Projects; one `Answer` row per respondent, the
  allocation as JSON), plus `QuestionGroup.budget` and `validation_settings['price']` on geo
  questions — no new geo type, so every map consumer works unchanged.
- One aggregate module feeds Responses, public results and export; a `budget` block on the public
  results page; export is one column per item plus a total, GeoJSON for placed items.
- Free on every plan: Split, Projects from a typed list, and budget groups (owner decision
  2026-11-10). Only a budget whose items are a reference layer's objects is gated by a new Pro
  feature `budget_map` in the features registry.
- Budget settings and item extras ride the ZIP, the REST API / MCP question schemas, the editor
  previews, the printable form (a paper shape per mode), and the respondent translations.

## Capabilities

### New Capabilities
- `budget-question`: the Budget family — modes, settings, item sources, what the respondent can
  and cannot do, what is stored, what is refused, the aggregates and the Pro gate.

### Modified Capabilities
- `question-type-picker`: the picker offers `budget` among the questions; the dialog shows the
  Budget block and the extended items table, and a geo question inside a budget group gets a Price block.
- `question-groups`: a group may carry a budget (total, unit, symbol).
- `response-data-export`: budget answers export as one column per item plus a total; placed items
  export as a point layer with `item` and `cost` properties.
- `public-results-page`: a `budget` block renders the mode's aggregate under the k-anonymity rule.
- `survey-serialization`: budget settings and the new item keys round-trip through the ZIP.
- `plan-entitlements`: the `budget_map` feature exists in the registry, Pro only, with a trial
  allowance.
- `printable-form`: a paper shape for each budget mode.

## Impact

- `survey/question_types.py` (two types, `GEO_TYPES`, `CHOICE_TYPES`, choice extras `description`,
  `cost`, `max_count`), `survey/models.py` (`Answer.allocation` JSONField, migration), `survey/forms.py`
  (widgets and fields), `survey/views.py::save_section_answers` (storage and refusal),
  `survey/budget_stats.py` (new aggregate), `survey/analytics.py`, `survey/public_results.py`,
  `survey/export.py`, `survey/serialization.py`, `survey/services/questions.py` + `QuestionForm`
  (`vs_budget_*` dialect), `survey/versioning.py` (structural changes), `survey/print/`,
  `api/v1/schemas.py` + `forms_bridge.py` + regenerated references, `billing/features.py`.
- Templates/JS: `budget.html`, the group bar in `question_group.html`, the price caption on the draw
  button, `js/budget_question.js`, group modal Budget block, question
  modal Budget block and items table, Responses and public results block templates.
- Tests: `survey/tests/test_budget_question.py` (new module ↔ spec), additions in the export,
  serialization, public results, printable-form and billing modules.
- Help centre page `how-to/budget-questions.md`; a What's new entry; the
  `/participatory-budgeting/` landing is a follow-up (copy, no tests).
