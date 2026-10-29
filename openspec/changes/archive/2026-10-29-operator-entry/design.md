## Context

Every answer enters through `survey_section` (`survey/views.py`): the respondent link creates a
`SurveySession` keyed in the browser session cookie, each section POST deletes and re-inserts that
session's answers, emits `SurveyEvent` rows, materialises shared-map layers and, on the thanks page,
marks the session completed. `opened_by_kind` (creator-funnel-events) says who *opened* the session
and is derived from the signed-in user; `survey_first_response` fires on the first `external` one.
Visibility is one engine, `survey/visibility.py`: `compute_visibility` walks sections → groups →
questions, a hidden item is "not applicable" server-side, and the editor shows the same verdicts.
Pro is a registry (`billing/features.py`) checked at the resource per request. Responses (v2) is
`SurveyAnalyticsService` over the version family; exports are writers over one `ExportBundle`.

Issue #355 (epic #350, item 1), widened by the owner on 2026-10-28: an **operator entry form** —
a Pro surface where a workspace member enters answers on someone's behalf (paper sheets after an
event, assisted interviews, field work), with sections/groups/questions the administrator reserves
for the operator. Design partner: a firm with two stacks of sheets printed from an archived version.

## Goals / Non-Goals

**Goals:**
- One entry flow for every "someone else enters the answers" case, producing ordinary sessions and
  answers that every read surface already understands.
- Operator sessions never touch the creator funnel, the respondent Perf data, shared maps or
  PostHog; they are separable everywhere answers are shown or exported.
- Operator-only structure decided by the administrator in the editor, judged by the existing
  visibility engine, travelling with every copy of the survey.
- Pro feature `operator_entry`, gated at the surface per request; nothing minted, nothing stored
  about the plan.

**Non-Goals:**
- Printable forms, photo/scan prefill, map alignment marks (epic items 2–4).
- Several answers from one sheet (workshop boards), table imports from other channels.
- Editing an entered session after *Finish* (own issue; the Responses answer editor already
  edits single cells).
- A second density/visibility mechanism, a kill switch, a per-operator role.

## Decisions

### D1. `SurveySession.source` is a new column, not a new `opened_by_kind` value
`opened_by_kind` answers "who opened" and is derived, never chosen; an operator-owner would be
`owner` by that rule, which is true and useless. `source` answers "where the answers came from":
`online` (every session the respondent link creates, the column default so history reads right),
`paper`, `assisted`, `field`, `other`. `entered_by` (FK `AUTH_USER_MODEL`, `SET_NULL`) is the
operator. **Alternative rejected**: a `paper` tag — tags are free text the creator edits, a filter
on them cannot be trusted and exports would need a parser.

### D2. One extracted save function, two callers
The section POST body (purge hidden answers, store by type, object answers) moves from
`survey_section` into `save_section_answers(post, session, session_survey, section, surface)`
in `survey/views.py` (same module, so its helpers stay where they are), returning the final
`VisibilityMap`. `survey_section` calls it and then does
what only respondents get: `emit_event`, `sync_question_layers_for_session`, redirects by
`completion_url`. The entry view calls it and nothing else. **Alternative rejected**: an `entry`
flag inside `survey_section` — the view already juggles the session cookie, embedding, HTMX, the
language picker and events; a flag there is where the next #388 comes from. The respondent view's
behaviour is unchanged byte for byte (its tests are the guard).

### D3. The entry session rides the URL, never the respondent cookie
`/editor/surveys/<uuid>/responses/enter/` (header form) creates the session and redirects to
`/editor/surveys/<uuid>/responses/enter/<session_id>/<section_name>/`. The view checks the session
belongs to the survey family, has `source != online` and the caller has the `editor` role; the
respondent cookie `survey_session_id` is neither read nor written. An operator who also opens the
public link in the same browser stays a respondent there. Section partials are re-used with
`entry=True` in the context: no language picker, no abuse footer, no embed carrier. `/editor/` is
a tracked prefix, so the entry views are added to `POSTHOG_EXCLUDED_VIEW_NAMES` like the previews
are: the page is a respondent page in shape and would otherwise record one session replay per
sheet.

### D4. Header: source, version, language; "Save and next sheet"
The header is the only operator-specific form: `source` (required), `version`
(`family_headers`, live by default; the session's `survey` becomes that header, which is how
archived-version routing already works), `language` (the survey's languages, defaults to the
primary). *Finish* on the last section sets `end_datetime` (`mark_completed`) and lands on a
"Saved" page with *Next sheet* (header prefilled from the previous entry through the query string)
and *Back to Responses*. Collection date, event name, sheet number live in operator-only questions
the administrator adds (D6) — no `collected_at` or `batch_label` columns (owner, 2026-10-28).

### D5. Soft validation = the form's `required` flag per surface
`SurveySectionAnswerForm(surface='operator')` builds respondent-facing fields with
`required=False` and operator-only fields with their own `required`. The respondent POST has no
error-render path (required is client-side today), so this one flag is the whole mechanism on both
sides. Structural checks stay: choice codes, geometry clamps, the visibility purge.

### D6. Audience lives in the visibility engine
`audience` on `SurveySection`, `QuestionGroup`, `Question`: `everyone` (default), `respondents`,
`operators`. `compute_visibility(survey, answers, surface='respondent'|'operator')` and
`popup_visibility(..., surface=)` fold it in as one more AND term: an item whose audience excludes
the surface is hidden, which already means "never rendered, never required, posted values
discarded, stored answers purged" (conditional-visibility). A section's audience hides its
members, a group's hides its questions, exactly as rules cascade. A hidden controller satisfies
nothing — an operator-only choice question therefore never shows respondents anything, with no
new rule. Client rule maps are unchanged (audience is static per surface, so the server simply
does not render the item). **Alternative rejected**: filtering questions in the form builder —
a second place that decides visibility, and the POST purge would disagree with the render.

### D7. Audience is a structural edit; its editor is not gated
`structural_question_changes` / `structural_section_changes` and the group equivalent add "the
audience" when it changes on a live survey, so a published survey goes through unpublished changes
(live-survey-editing). The control sits in `_visibility_block.html` beside the rule (one
"Who sees this" block), with a badge on list items. The editor is open to Free: an administrator
prepares the operator section, pays when someone enters (D8).

### D8. Pro gate at the surface
`operator_entry` in `FEATURES` for `pro`. The header and every entry URL are wrapped in
`require_feature('operator_entry', org_getter=<the survey's organisation>)` after
`survey_permission_required('editor')`; a lapsed subscription gets the existing 403 with the
upgrade hint, sessions already entered stay. The Responses toolbar shows the button to editors;
without the feature it carries the lock and links to billing (`has_feature`).

### D9. Operator sessions on read surfaces
They are answers: Overview counts, question stats, public results (clean-session aggregates),
exports and the table include them; a `source` column (after Status, values filter
`cf_source=v:paper|assisted`) and the drawer's "Entered by <name>, <source>" make them separable.
They are not respondents: `signals.py` skips any `source != online` for `survey_first_response`
(and does not count them as "already answered"), `record_demo_open` is not called,
`sync_question_layers_for_session` returns at once for them (a keyed-in mark on a shared map is
epic item 3's call), `PerformanceAnalyticsService` reads `SurveyEvent`, which they never write —
a test pins that no event row exists for an entry session. Empty operator sessions (header
submitted, nothing entered) are empty sessions like any other: hidden by default, trashable.

### D10. Travel
`audience` is a plain field: `plain_field_values` carries it into the draft copy, duplicates and
paste (`DraftCopyKeepsFieldsTest` proves it), `serialization.py` writes and reads it (missing key
= `everyone`), API/MCP schemas get `audience: Literal[...]` with `extra='forbid'`, `out.py`
returns it, the translation table lists operator items as ordinary rows. The responses ZIP file
and `SESSION_COLUMNS` gain `source` and `entered_by` (username — never an email).

## Risks / Trade-offs

- [The respondent POST body is 200 lines with many local names] → extract with zero behaviour
  change first, run `survey.tests.test_answer_persistence` + geo/object tests, commit separately.
- [An administrator marks a controller question `operators` and respondents lose a branch] → it is
  the documented cascade; `lint_rules` adds a warning "controller is not shown to respondents"
  badge so it is visible in the editor.
- [Operators entering on an archived version see questions deleted since] → intended: the sheet
  matches that version; Responses already spans versions by lineage.
- [An operator session on a `testing` survey or a closed one] → allowed: closed surveys are exactly
  where sheets get entered; `check_survey_access` is not on this path and must not be.
- [PostHog session replay of the entry page] → excluded by view name (D3).
- [`required=False` on respondent fields lets an operator skip everything] → by design; the
  administrator who wants a hard field makes it operator-only.

## Migration Plan

Additive migration `0109`: three `audience` columns with default `everyone`, `source` default
`online`, nullable `entered_by`. No backfill, no data rewrite. Deploy is one release; rollback is a
revert (columns stay, unused). No feature flag: the Pro entitlement is the switch.

## Open Questions

- Should an operator-only choice question be offered as a controller at all in the rule picker, or
  listed with a note? (Default: listed, with the lint warning.)
- Whether `field` deserves its own source value or folds into `assisted`. Kept separate: a field
  worker's own observation is not an interview.
