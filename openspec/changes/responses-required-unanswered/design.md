## Context

Responses v2 computes, on every table render, five session issues (`compute_session_issues`:
empty, incomplete, missing_required, fast, duplicate) and six per-answer lints
(`compute_answer_lints`: self_intersection, empty_required, out_of_range, numeric_outlier,
short_text, area_outlier). They feed the Issues chip and per-type menu, the Overview "flagged" KPI,
the Responses-tab badge and the Needs-review feed. Production numbers in #691 show that 75 % of
answered sessions carry an issue, mostly false (Incomplete, Duplicate).

"Completed" is a separate rule — "has an answer row in its version's last section" — written once
in `analytics.completed_session_filter` and copied inline in `family_completion_counts`
(dashboard cards) and `SurveyAnalyticsService._last_section_ids` (trend `c`, session-hours
flag). The export's `completed_only`, the REST summary and MCP reach it through
`export.excluded_sessions` / `response_scope.responses_scope`.

Facts found while mapping the code that shape this design:

- **Required is enforced only in the browser** (`base_survey_template.html` `htmx:configRequest`).
  The section POST has no server check and Back skips the client one; operator entry makes
  required soft. So unanswered required questions already exist in stored data and the stored
  answers are the only truth.
- **`required` is a safe live edit** (`versioning.structural_question_changes` ignores it), as are
  `min_features` and `min_objects`. A creator can make a question required on a published survey
  with responses, in place.
- **Publishing moves the canonical survey's sessions, sections and questions to the new archived
  header** (`versioning.publish_draft`), so a session is always judged against the structure it
  was answered on; publishing itself changes no session's state.
- All three answer surfaces (respondent, operator entry, paper entry) write through one function,
  `views.save_section_answers`, which already returns the final `VisibilityMap`.
- `min_value` / `max_value` on number questions are read only by the `out_of_range` lint; nothing
  enforces them for respondents. Range questions take their bounds from their choices.
- `PerformanceAnalyticsService` (Perf pane, tracked-link `started`/`completed`, median completion
  time) counts `SurveyEvent`s — a customer-facing funnel feature that stays as it is.

## Goals / Non-Goals

**Goals:**
- One definition: a session's *missing required questions* = required top-level questions of its
  version, visible to that session, without a stored answer that satisfies them. *Completed* =
  not empty and no missing required question. Every surface that says "completed" uses it.
- Cheap to read in bulk (dashboard cards for many surveys, Overview, table filters, export, API).
- Quiet presentation: a marker with a tooltip naming the questions; "Shape edges cross" note on
  polygon answers. Nothing else from Issues/lints survives.
- Number Min/Max become a respondent constraint (owner decision 2026-11-16).

**Non-Goals:**
- Server-side enforcement of required questions on the section POST (would change respondent
  flow; the marker reports what was stored).
- Detecting repeat submissions. If it is ever wanted, it is a separate change based on a
  first-party per-browser id, shown as a fact, never a delete suggestion.
- Changing `SurveyEvent`-based numbers (Perf pane, tracked links, median completion time).
- Deleting the legacy (`RESPONSES_V2=False`) Responses page. It loses the same Issues pieces
  through the shared partials and follows the same completion rule.

## Decisions

### D1. Store the result on `SurveySession`

Two new columns (migration `0131`):

- `required_missing` — `JSONField(default=list)`: question **codes** of the missing required
  questions, in survey order. Codes, not ids: they are what the tooltip, the export and the
  translation table already use to address questions, and a session's header never changes
  after the session exists, so a code resolves to exactly one question of `session.survey`.
- `required_complete` — `BooleanField(default=True, db_index=True)`: `required_missing == []` (both defaults agree, so a row never refreshed still reads consistently),
  kept as its own indexed column so querysets filter and aggregate on a boolean
  (`Count(filter=Q(required_complete=True))`) instead of JSON equality.

*Completed* is then `nonempty_sessions(qs).filter(required_complete=True)` — one queryset
helper, `completed_session_filter(qs)` (the `headers` argument goes away). The emptiness test
stays the existing `Exists` helper rather than being folded into the flag, so "empty" keeps
exactly one definition (`responses-empty-sessions`).

*Alternatives considered.* Computing on read: the visibility engine runs in Python per session,
and the dashboard cards, Overview and API summary need counts over thousands of sessions across
many surveys in a fixed number of queries — not feasible. Storing only the boolean: the tooltip
would then recompute visibility per row on every table render; the list is small and makes the
tooltip free.

### D2. One function computes it: `survey/required_state.py`

```
missing_required(session, *, vmap=None, answers=None) -> list[str]   # pure-ish, no writes
refresh(session, *, vmap=None) -> None                               # computes and saves both columns
refresh_many(sessions_qs) -> int                                     # batched, grouped by header
```

Rules (mirroring what the respondent form asks for):

- Surface: `SURFACE_OPERATOR` when `session.is_operator_entry`, else `SURFACE_RESPONDENT`, so an
  operator-only question counts for a paper sheet and is invisible to an online respondent.
  The *required* flag is the question's own `required`, not the operator form's soft required:
  a paper sheet that skipped a required question is missing it.
- Visibility: `visibility.compute_visibility(session.survey,
  answers_by_code_for_session(session), surface=…)`; candidates are top-level questions of
  `vmap.visible_sections` with `vmap.is_question_visible(q.id)` (sections, groups, own rules and
  audience). Broken rules fail open, as everywhere.
- Candidates: `q.required` and type not in (`html`, `image`); plus `layer_objects` questions with
  `min_objects > 0` (their `required` is forced off; the minimum is the requirement).
- Satisfied when the session holds, for that question:
  - geo types with `validation_settings.min_features`: at least that many top-level answer rows;
    other geo types and every other type: at least one top-level answer row carrying a value
    (text/number not blank, non-empty `selected_choices`, geometry/multipoint/upload/allocation
    present). Inline editing can leave a blank row behind; it does not count.
  - `layer_objects`: answers on its sub-questions about at least `min_objects` distinct
    `layer_object`s.
- `refresh` reuses the `vmap` that `save_section_answers` already computed when given.
- `refresh_many` loads each header's structure once and the sessions' answers in one query per
  chunk, for the backfill and for a survey-wide recompute.

### D3. When it is recomputed

| Event | Where | Scope |
|---|---|---|
| Section POST (respondent, operator entry, paper entry; forward and Back) | end of `views.save_section_answers`, after object answers are saved | that session |
| Inline answer edit on Responses | `analytics_answer_edit` | that session |
| Paper review supersedes machine answers | `paper/review.py::supersede_machine_answers` | that session |
| ZIP import of responses | `serialization.import_responses_from_archive` | imported sessions |
| A question's `required`, `min_features` or `min_objects` changes, or a question with answers is deleted | `services/questions.py` update/delete, `transaction.on_commit` | every non-empty session of that header (`refresh_many`) |
| Backfill | data migration `0132` | every non-empty session |

The survey-wide recompute runs after commit, inside the request for a survey of up to
`SYNC_LIMIT` (1000) non-empty sessions — the creator's next page already shows the new numbers —
and otherwise as a Celery task (`recompute_required_state(header_id)`) with the same synchronous
fallback the content-screening notice uses when the broker refuses the task, so a refused enqueue
never leaves stale flags. Besides `required` and the two minimums, a change of a question's rule,
audience or type and the creation of a required question also trigger it (they happen in place
only on a survey that is not live, whose test sessions they affect). Publishing and restoring a version need no recompute:
sessions move with the structure they were answered on (see Context). Trash and restore do not
touch answers.

*Alternative considered.* A per-header "structure version" stamp compared on read, recomputing
stale sessions lazily. More moving parts for the same result; the list of in-place edits that
change the required set is short and covered by tests (D7).

### D4. Presentation

- **Table**: the `issues` system column becomes `required` (v2 and legacy). A row with missing
  questions shows a small neutral marker (muted text colour, `far fa-circle-question`-style icon,
  no red, no count chip) whose `title` / tooltip reads "Didn't answer N required question(s):
  *name*, *name*". Names come from the session header's questions by code
  (`Question.name`, plain text, escaped). Sorting and the free-text haystack use the names.
  Empty rows keep their "Empty" badge and get no marker.
- **Shape edges cross**: `compute_answer_lints` shrinks to `crossed_shapes(answers)` →
  `{sid: {question_key}}`, computed in `get_table_page` as today (GEOS `.valid` on polygon
  answers). The cell keeps its current lint highlight in a neutral style with the tooltip "The
  edges of this shape cross each other. It may not open correctly in GIS software." The legacy
  `lint_tooltip` filter keeps only this text.
- **Filter**: query param `required=missing` replaces `issues=`. Toolbar chips become
  All / Complete / Required unanswered / Trash, where Complete and Required unanswered partition
  the shown non-empty rows. The phone sheet loses its Violations section and gets the same two
  options. `issues=` in an old URL is ignored.
- **Overview**: KPI strip = responses, completion rate, median time, map features. The flagged
  tile, the Responses-tab badge and the Needs-review block are removed (a "needs review" list is
  exactly the alarm the owner asked to drop); Latest responses keeps the validation-status chip.
  Trend `c` and the session-hours `completed` flag read `required_complete`.
- **Bulk trash / permanent delete**: the browser `confirm()` becomes the app's delete modal
  (`editor.html #deleteModal` look): "Move 37 responses to trash?" / "Permanently delete 37
  responses? This cannot be undone.", Cancel + `btn-danger`. The count is the number of selected
  rows sent to the endpoint.

### D5. What is deleted

- `compute_session_issues`, the `incomplete` / `missing_required` / `fast` / `duplicate` rules,
  `_last_section_ids` / `_get_last_section` uses for completion, `flagged_count`,
  `anomaly_counts`, `_WARNING_TYPES` / `_ERROR_TYPES`, `issues_filter` handling,
  `v2_counts['issues']`.
- Templates/JS: `_ANOMALY_ERRORS` / `_ANOMALY_WARNINGS`, the anomalies sidebar/strip machinery,
  `rv2IssuesMenu`, `.rv2-issues-*` CSS, the legacy toolbar Issues select and pills, the
  validation-settings cog, `#validationSettingsModal`, `openValidationSettings` /
  `saveValidationSettings`, the dead `selectAllFlagged`.
- `analytics_validation_settings` view and URL; `SurveyHeader.validation_settings` stays as a
  column (no destructive migration in the same deploy) but nothing reads or writes it.
- Question settings `outlier_sigma`, `min_length`, `area_outlier_factor`: removed from
  `parse_validation_settings`, the question modal, `ValidationSettingsIn` and the forms bridge.
  Stored keys are left in the JSON and ignored (no data migration).

### D6. Number Min/Max for respondents

`SurveySectionAnswerForm` passes `min` / `max` attributes to the number input from
`validation_settings.min_value` / `max_value`, so the browser refuses an out-of-range value
before the POST (consistent with how required works today). `save_section_answers` drops a
number value outside the bounds (a tampered or script POST), like it drops blanks. The question
modal shows Min/Max for number questions only (range takes bounds from its choices). Paper and
operator entry use the same form, so the same bounds apply.

### D7. Tests

New module `survey/tests/test_responses_required_unanswered.py` (one module per capability):
the rules of D2 (hidden by a section rule, by a group rule, by audience; operator-only question
on a paper sheet; geo minimum; `min_objects`; blank inline-edited row), every trigger of D3
(including toggling `required` on a published survey with responses), the four-surface agreement
(Overview completed count = table "Complete" chip = `completed_only` export rows = API summary
`completed`), the marker tooltip, the filter, and the bulk-delete modal text. Existing tests of
removed behaviour are deleted with it, tests of changed definitions are updated
(`test_response_validation_management.py`, `test_responses_empty_sessions.py`,
`test_analytics_data_workspace.py`, `test_responses_navigation.py`, `test_responses_overview.py`,
`test_survey_analytics_basic.py`, `test_cross_version_analytics.py`, `test_survey_editor.py`,
`test_responses_export_formats.py`, `api/tests/test_v1_responses.py`).

## Risks / Trade-offs

- [Backfill runtime in pre-deploy] → `refresh_many` batches by header and skips empty sessions
  (≈70 % of rows); measure on a production-sized local copy before merge and record the time in
  the PR. If it exceeds a minute, move the backfill to a Celery task enqueued by the migration,
  with readers treating "not yet computed" via a nullable `required_complete` — decided before
  merge, not after.
- [A future in-place edit that changes the required set is added without a recompute] → the
  trigger list lives in one place (`required_state`), and a test toggles each known setting on a
  published survey with responses.
- [Completion rates jump on many surveys overnight] → What's new card explains it; the old
  definition is gone everywhere at once, so no two surfaces disagree.
- [API clients sending `outlier_sigma` / `min_length` / `area_outlier_factor` get 422]
  (`extra='forbid'`) → acceptable: the API is weeks old, agents read the schema from
  `tools/list`, and accepting-and-ignoring would document settings that do nothing. Regenerate
  `reference/api.md` and `reference/mcp-tools.md`.
- [Min/Max on existing number questions start blocking respondents] → this is what creators set
  them for; the What's new card mentions it in one sentence.
- [Data-migration imports app code] → the migration calls `required_state.refresh_many` with
  current models; acceptable for a one-off backfill, and the function is kept free of fields
  added later than `0131`.

## Migration Plan

1. `0131`: add `required_missing`, `required_complete` (defaults, no table rewrite of values).
2. `0132`: backfill every non-empty session through `refresh_many`, in chunks of 500.
3. Deploy; the What's new entry ships in the same PR.
4. Rollback: revert the PR. The two columns are additive and harmless to old code; the old code
   recomputes issues on read and never touches them.
5. After deploy (outside the repo): rerun the ops `affected_trash.sql` and write personally to
   creators with Duplicate-flagged responses in their trash (Stack #386).

## Open Questions

- None blocking. The legacy Responses page removal is a separate issue if wanted.
