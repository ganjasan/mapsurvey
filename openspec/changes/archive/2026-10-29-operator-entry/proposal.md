## Why

Answers that did not come in through the respondent link have no way into a survey today. A
design-partner firm holds two stacks of filled paper sheets (two events, two languages) printed
from an earlier published version of their survey; a consultant interviewing an elderly resident
by phone, a field worker placing a point for the person next to them, a clerk keying in open-house
boards — all of them can only use the public link, where their sessions count as online answers on
the current version, fire the creator's first-response milestone and distort the funnel. Issue
#355 is the first item of epic #350 (paper responses); the owner widened it on 2026-10-28 from
"paper entry" to an **operator entry form**: a Pro surface on Responses where a workspace member
enters answers on someone's behalf, with fields the survey administrator reserves for the operator.

## What Changes

- **Operator entry mode** on the Responses page (editor role and up, Pro feature `operator_entry`):
  the survey renders in entry mode, one sheet or interview at a time, and *Finish* stores a normal
  `SurveySession` with its `Answer` rows. A header before the first section fixes what a respondent
  never chooses: the **source** (`paper` / `assisted` / `field` / `other`), the **survey version** the
  sheet was printed from (archived versions allowed, live by default) and the **sheet language**.
  *Save and next sheet* keeps the header for the following entry.
- **Session source is first-class**: `SurveySession.source` (`online` for every session created by
  the respondent link; the operator values above) and `entered_by` (the signed-in operator).
  `opened_by_kind` keeps answering "who opened" and is untouched. The source rides `tags`-free:
  no magic tag.
- **No respondent side effects** for an operator session: no `SurveyEvent` rows, no
  `survey_first_response`, no demo-open row, no shared-map materialisation, no PostHog; the Perf
  pane and every funnel ignore operator sessions. Responses counts, Overview, public results and
  exports include them as answers — they are answers.
- **Soft validation in entry mode**: a respondent-facing `required` never blocks *Finish* (a blank
  on paper is a blank); structural validation (choice codes, geometry, visibility purge) is the
  respondent page's. `required` on an operator-only question does block, because it is the
  operator's own field.
- **Audience on structure** (`SurveySection.audience`, `QuestionGroup.audience`,
  `Question.audience`: `respondents` / `operators` / `everyone`, default `everyone`). The
  administrator decides which sections, groups and questions exist only on the operator form
  ("Sheet number", "Event", "Collected on", "Illegible answer"). The respondent page treats an
  `operators` item exactly as a hidden one (never rendered, never required, posted values
  discarded); the operator form renders every audience. Audience is judged inside the one
  visibility engine, not beside it. Changing the audience on a live survey is a **structural**
  edit (unpublished changes); the audience editor itself is not Pro-gated.
- **Responses and exports show the source**: a *Source* column on the table, a `source` filter
  (online / paper / assisted / field / other), `source` and `entered_by` in every session export
  and in the ZIP responses file; the detail drawer names the operator.
- **Travel**: `audience` rides the draft copy, duplicate/paste, ZIP export/import, the REST API
  and MCP (same schemas), the translation table (operator items are ordinary rows). AI generation
  writes no audience.
- **Help**: a how-to page on the help site ships with the change. No "What's new" card here:
  one card covers the whole epic #350 (owner, 2026-10-29).

## Capabilities

### New Capabilities
- `operator-entry`: the entry surface on Responses — who may open it, the header (source, version,
  language), the entry flow and *Save and next sheet*, soft validation, which side effects are
  suppressed, how operator sessions are stored, shown, filtered and exported, and the Pro gate.
- `question-audience`: the `audience` attribute on sections, groups and questions — what each value
  means on each surface, its editor control and badge, the structural-edit rule, and how it travels
  with copies, archives, the API and the translation table.

### Modified Capabilities
- `creator-funnel-events`: sessions carry a `source` beside `opened_by_kind`; `survey_first_response`
  and every creator milestone ignore operator sessions, which neither emit nor suppress one.
- `conditional-visibility`: the server-side "hidden items are not applicable" rule covers items whose
  audience excludes the current surface; the engine's verdict takes audience into account.
- `plan-entitlements`: the registry contains `operator_entry` for plan `pro`.
- `response-data-export`: session metadata includes `source` and `entered_by`.
- `survey-performance-analytics`: funnel and Perf KPIs count respondent-link sessions only.
- `survey-serialization`: `audience` round-trips on sections, groups and questions; the responses
  file carries `source` and `entered_by`.
- `rest-api-v1`: section, group and question schemas accept and return `audience`.
- `shared-map-layer`: operator sessions are not materialised into question-sourced layers.

## Impact

- **Models / migration**: `SurveySession.source` + `entered_by` (FK user, SET_NULL),
  `audience` on `SurveySection`, `QuestionGroup`, `Question`; migration `0109`. Existing sessions
  read `online`, existing structure `everyone`.
- **Respondent path**: `survey/visibility.py` (audience inside `compute_visibility` /
  `popup_visibility`, a `surface` argument), `survey/forms.py` (`SurveySectionAnswerForm` builds
  for a surface; soft required), `survey/views.py` (the section view passes the respondent surface;
  no behaviour change for respondents).
- **Entry surface**: new module `survey/operator_entry_views.py` + templates under
  `editor/operator_entry/`, URL under `/editor/surveys/<uuid>/responses/enter/`; reuses the
  section partials and `js` of the respondent page with an `entry` flag; `billing/features.py`,
  `billing/gates.py`.
- **Structure editing**: `survey/editor_forms.py` (`SurveySectionForm`, `QuestionGroupForm`,
  `QuestionForm`), `survey/services/{sections,groups,questions}.py`, `survey/versioning.py`
  (`structural_*_changes`, snapshots), the three modals and `_visibility_block.html` (audience
  control next to the rule), list-item badges, `editor_question_preview_live`.
- **Read surfaces**: `survey/analytics.py` (table column, filter, Perf exclusion),
  `survey/analytics_views.py`, `survey/export.py` (`SESSION_COLUMNS`), `survey/serialization.py`,
  `survey/public_results.py` (no change: clean sessions already include operator ones),
  `survey/signals.py`, `survey/layers.py` (`sync_question_layers_for_session` guard).
- **API platform**: `api/v1/schemas.py`, `api/v1/out.py`, `api/v1/forms_bridge.py`,
  `scripts/build_api_reference.py` and `scripts/build_mcp_reference.py` outputs
  (`ApiReferenceFreshnessTest`, `test_reference`).
- **Cloning**: nothing — `plain_field_values` carries `audience`; `DraftCopyKeepsFieldsTest`
  covers it.
- **i18n**: new creator strings in every offered catalog (`TranslationCatalogHygieneTest`).
- **Help**: `help/src/content/docs/how-to/enter-responses-for-others.md` + `survey/help_links.py`
  key `operator_entry`.
- **Tests**: `survey/tests/test_operator_entry.py`, `survey/tests/test_question_audience.py`
  (new capabilities → new modules, `SpecTestLineageTest`), deltas in the modified capabilities'
  modules, `billing/tests/test_plan_entitlements.py`, `api/tests/`.
- **Out of scope** (epic #350 items 2–4 and open questions): printable form, photo/scan
  prefill, map alignment marks, multi-answer workshop sheets, imports from other channels,
  editing an entered session after *Finish* (own issue).
