## Context

The Responses page (`RESPONSES_V2`, default on) reads its sessions through
`SurveyAnalyticsService` (`survey/analytics.py`). Its `base_qs` — non-deleted sessions of the
version scope — feeds every session count on the page: the KPI strip and the Responses tab badge
(`get_overview`), the Overview feeds, median duration, the 7-day trend (`get_overview_extras`,
`get_hourly_sessions`), and the table (`get_table_page`: chip counts, sequence numbers, issues,
pagination). Answer aggregates (charts, map, object stats, the cross-filter matrix) already skip
empty sessions because they read `Answer` rows.

"Empty" exists today only as an issue: `compute_session_issues` marks a session `empty` when it
has no `Answer` with `parent_answer_id IS NULL`, and the v2 Issues menu offers "Empty sessions".

Every export format goes through one gate, `survey/export.py::excluded_sessions`, applied inside
`_collect_part` to geo features, session rows, files and object sheets.

The section POST drops only exact `''` values (`survey/views.py` main loop and
`_parse_object_fields`), so whitespace-only text is stored as a top-level answer, and a
whitespace-only number reaches `float()` and raises.

## Goals / Non-Goals

**Goals:**
- One definition of "empty session", one helper, used by the Responses page, the issue
  computation and the export.
- The v2 Responses page hides empty sessions by default and says so with a number and a toggle.
- Exports never carry empty sessions.
- Whitespace-only text stops creating answers.

**Non-Goals:**
- Funnel and Perf pane (`SurveyEvent`, `PerformanceAnalyticsService`): untouched.
- The legacy Responses dashboard (`RESPONSES_V2=False`): untouched. It is the rollback state and
  keeps the old behaviour.
- The editor survey list and dashboard session counts (`views.py` family counts,
  `editor_views.py` `session_count`): untouched.
- Public results `response_count`: untouched in this change (see Open Questions).
- Bulk delete, data migration of the 15 legacy blank-answer sessions, "in progress vs abandoned"
  (#105).

## Decisions

### D1. One helper: `analytics.nonempty_sessions(qs)` / `empty_sessions(qs)`

A queryset filter on `Exists(Answer.objects.filter(survey_session=OuterRef('pk'),
parent_answer_id__isnull=True))`. Layer-object answers are top-level rows and moderator-hidden
answers are rows, so both count as answers without special cases. `compute_session_issues`,
`SurveyAnalyticsService` and `excluded_sessions` all call it.

*Alternative*: a denormalised `has_answers` flag on `SurveySession`. Rejected: needs a migration,
a backfill, and a write on every section POST and answer delete; `Exists` over the indexed
`survey_session_id` FK is cheap at the sizes we have (largest survey ~2.5K sessions).

### D2. Filter at `base_qs`, behind `include_empty`

`SurveyAnalyticsService.__init__(..., include_empty=True)`. When False, `base_qs` keeps only
non-empty sessions, so KPIs, feeds, trend, sequence numbers and the table follow without touching
each method. The default stays True so every other caller (survey list, legacy dashboard, tests)
behaves as before; only the v2 view passes the creator's choice. The service also exposes
`empty_count` — empty sessions in scope, computed over the unfiltered scope — for the headline.

`_stats_language` and the trash branch of `get_table_page` build their own querysets; the language
stats get the same filter, trash does not (trash is "everything I deleted", empty or not).

### D3. The choice lives in a cookie, not the URL

The toggle must reach both the server-rendered page (KPIs, feeds, trend) and the HTMX table
request. A query parameter would need threading through the version select (which overwrites
`location.search`), the table state form and every deep link. A per-browser cookie
`rv2_show_empty=1` is read by `analytics_dashboard` and `analytics_table` alike, survives
reloads and version switches, and satisfies "remembered per browser" with no redirect flash.
The toggle sets or clears it and reloads the page.

*Alternative*: localStorage + URL rewrite on load. Rejected: the server renders first, so the
page would flash the wrong numbers and reload.

### D4. Headline: two numbers where the creator already looks

When empties are hidden and there is at least one, the KPI strip's responses card and the table
chip row show "N responses · M opened without answering" with a "Show" control; when shown, the
line reads "… (shown)" with "Hide". The Responses tab badge counts what the table shows. With
zero empty sessions in scope nothing extra renders.

The Overview empty state ("No responses yet") also renders when every session in scope is empty,
and then states "M opened without answering" with the Show control, so a survey whose visitors all
left does not look untouched.

### D5. Sequence numbers count responses, and empty rows carry none

Today `#N` is the rank over `base_qs`. With D2 it becomes the rank among non-empty sessions in
scope — so the newest response is `#<headline count>`, which is the number the creator was
asking for. When empties are shown they render with no number ("—"), so toggling never renumbers
responses. `comments.session_seq` switches to the same rule (non-empty only); a comment anchored
to an empty session is labelled "Response without answers" instead of a number.

Known effect: a session that gets its first answer later is slotted in by start time and shifts
later numbers by one. Accepted; it is how the rank behaves under a version filter today.

### D6. "Empty sessions" leaves the Issues menu

Hidden empties make the Issues entry permanently zero; the toggle is the control for them. The
`empty` issue key stays in `compute_session_issues` (rows still show the "Empty" badge when
empties are shown, and `incomplete`/`missing_required` still skip them), but the v2 Issues menu
and the mobile sheet stop offering it. The legacy select keeps it (non-goal: legacy untouched).

### D7. Export: empties always excluded

`excluded_sessions` adds `empty_sessions(qs)` unconditionally — before and regardless of
`include_all` and `completed_only`. The dialog's "Include excluded responses" hint keeps naming
trashed and not-approved; one line under the switches says sessions without answers are never
exported.

### D8. Whitespace: test the stripped value, store the stripped value

In the main POST loop the blank filter becomes `v.strip() != ''` and `text`, `text_line`,
`datetime`, `number`, `range` store the stripped value; the same in `_parse_object_fields`. Choice,
geo and file values are opaque tokens and pass through unchanged apart from the blank test.
Geo sub-answer properties are child rows and do not affect emptiness; their `float(' ')` is left
for a separate fix.

## Risks / Trade-offs

- [Creators who used the session count as a reach metric see it drop overnight] → the headline
  states the hidden number next to it, and a changelog entry explains why (#227 mechanism).
- [Sequence numbers change once on deploy; screenshots and notes that say "#57" go stale] →
  accepted; the changelog entry mentions it. Comment labels follow the same rule, so in-app
  references stay consistent.
- [A respondent still mid-survey (no answer yet) is hidden] → it appears the moment it saves an
  answer; the toggle shows it earlier.
- [`Exists` subquery on every Responses query] → indexed FK; measure `get_table_page` on the
  largest production survey copy before merging.
- [Public results still say 350 while the editor says 146] → flagged as an open question.

## Migration Plan

No schema change. Deploy is the rollout. Rollback = revert the PR; there is no stored state
besides the cookie, which an old build ignores.

## Open Questions

- Should the public results page's "N responses" (`PublicResultsService._collect_clean_session_ids`)
  also count only sessions with an answer? It counts empty sessions today, so after this change
  the public number will be higher than the editor's. Left out of this change pending the owner's
  call.
