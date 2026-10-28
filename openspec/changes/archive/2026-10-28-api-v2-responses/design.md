## Context

- `SurveyAnalyticsService` (survey/analytics.py) computes the Responses Overview: `get_overview()`,
  `get_question_stats(q)` with handlers per type (`_stats_choices`, `_stats_number`, `_stats_text`,
  `_stats_geo`, `_stats_layer_objects`). The handlers filter answers only by lineage and
  `is_deleted=False` — they ignore `base_qs`, so empty/`not_approved` sessions count. Geo questions
  and their sub-questions are not in `get_all_question_stats()`.
- `survey/export.py`: `version_parts()` → `excluded_sessions()` → `collect()`; `collect` builds a
  `GeoLayer` (FeatureCollection with sub-question values as properties) for every geo question;
  `export_response()` returns the file response.
- Moderation: `SessionValidationService.set_status` (+ `rebuild_question_layers_for`), called from
  `analytics_session_set_status` / `analytics_bulk_set_status`, which write no audit row.
- REST v1 already lists responses (`api/v1/data.py`) and streams exports; scopes live in
  `api/scopes.py`; the consent page treats `DANGEROUS_SCOPES` as off-by-default switches with the
  note "This cannot be undone".

## Goals / Non-Goals

**Goals:** an agent can produce a full report — numbers, distributions, geometry, text — and hand
over a file; the numbers equal the file's; moderation is possible under its own right.

**Non-Goals:** editing answers; trash/restore/hard delete over the API; `Answer.hidden` comment
moderation and `LayerObject.status` (block 3, layers); per-respondent analytics (`SurveyEvent`).

## Decisions

### D1 · One session scope: the export's
`responses_scope(survey, version, include_all, completed_only)` in a new `survey/response_scope.py`
returns the session queryset the export would include — built on `version_parts()` and
`excluded_sessions()` so it cannot drift from the file. Summary, text answers, GeoJSON and
`list_responses` (when the new flags are given; its defaults stay) all use it.

### D2 · Stats over a session subset, editor unchanged
`SurveyAnalyticsService(..., sessions=None)`: when given, every `_stats_*` handler adds
`survey_session_id__in=sessions`. `None` keeps today's behaviour for the editor and every other
caller. *Alternative*: change the Overview too — rejected for this change (owner: API only).

### D3 · Summary shape
`{scope: {version, include_all, completed_only}, responses, completed, completion_rate,
questions: [...]}` in section order. Each question: `id, code, section_id, name, type, answered`
plus per type — choices: `choices: [{code, label, count, current}]` and, when the question has an
"other" option, `other_texts: [{text, count}]` (top 50, case-folded, trimmed); number/range:
`count, mean, median, min, max`; rating: choices plus `mean`; text: `answered` only (texts via the
answers route); geo: `features` (count) and `subquestions: [...]` (same shapes, over the
sub-answers); `layer_objects`: `objects: [{key, title, answers, subs}]` from `object_aggregates`.
No ORM objects, no `*_json` copies; `html`/`image` blocks are skipped.

### D4 · Per-question GeoJSON from the export collector
`export.collect_question(survey, question, sessions)` runs the existing `_collect_part` logic for
one geo question across the version family and returns the merged FeatureCollection (CRS84,
sub-question properties, `session`, `validation_status`, spray `dot_count`/`area_m2`). Cap: 5 000
features per call, `truncated: true` beyond — the full set is the export.

### D5 · Export link: signed, 15 minutes, built on GET
`POST /export-link` returns `{url, expires_at}`; the token is `signing.dumps({s: survey uuid, u:
user id, t: token id, f: format, v, a, c, x: files}, salt='api.export-link')`, `max_age=900`. `GET
/api/v1/export-links/<token>` (no bearer — the link is the credential) loads the user, re-checks the
survey role (`viewer`+), the Pro gate on the owning workspace and that the issuing token is not
revoked, counts against `cap.export`, then returns `export.export_response(...)`. Nothing is
stored. The link is reusable within 15 minutes (a chat preview or a mail scanner may fetch it
first). Never logged with its query: the token travels in the path, and `_posthog_scrub_tags`
already keeps API paths only by prefix — the route is added to that prefix list.

### D6 · Moderation under `responses:moderate`
New scope `responses:moderate` ("Approve, hold or reject responses"), not in `DEFAULT_SCOPES`. It
joins the consent switches through a new `SWITCH_SCOPES` (= dangerous ∪ moderate); the note per
switch comes from `SWITCH_NOTES` — publish/delete keep "This cannot be undone…", moderate says
"Rejected responses leave exports and public results; you can change it back." `PATCH
/responses/{id}` with `{validation_status}` requires survey role `editor`, the session must belong
to the survey's version family (404 otherwise), calls `SessionValidationService.set_status`
(which rebuilds shared-map layers) and writes `audit.record(actor, 'response_status', survey,
session_id, from, to)`. The editor's two status views write the same row through `audit()`.

### D7 · Limits and events
Reads count as `api.read`; the summary is heavy (`get_overview` runs `compute_session_issues`) —
the summary does NOT call `get_overview()`; it counts responses/completed directly from the scope.
Export link creation counts against nothing; the download counts against `cap.export` and emits
`data_exported` with `surface='api_link'`. Moderation counts as `api.write`.

### D8 · MCP (PR 2)
Tools wrap the routes' functions (shared helpers in `api/v1/responses.py`), results in
`{note, data}`. `get_response_summary` and `list_text_answers` are where respondent text enters
the model's context — the note already says data, not instructions. `moderate_response` needs no
`confirm` (reversible).

## Risks / Trade-offs

- [A leaked export link in a chat transcript] → 15 minutes, rights re-checked, revoking the token
  kills it, nothing stored.
- [Summary cost on big surveys] → no `compute_session_issues`; one query per question (as the
  Overview); `api.read` limits.
- [Numbers differ from the editor's Overview] → by design (D2); documented in the reference: the
  API counts what the export counts.
