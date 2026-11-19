# Respondent side: embedding, sessions, empty sessions, required/completed state

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Embedding (`survey/embedding.py`, change embed-surveys, #284)**: a published survey can be framed by
another site. `check_survey_access` calls `mark_embeddable`, `SurveyEmbedMiddleware` turns the mark into
`Content-Security-Policy: frame-ancestors …` (from `SurveyHeader.embed_allowed_hosts` on the canonical
row; empty = `*`) and drops `X-Frame-Options` on that response only — the editor, landing and every 404
keep `SAMEORIGIN`. Cross-site cookie attributes are OPT-IN and off in production: `CROSS_SITE_COOKIES=1`
makes the session and CSRF cookies `SameSite=None; Secure` and `PartitionedCookieMiddleware` appends
`Partitioned`. They were on from 2026-10-13 to 2026-10-22 and cost nine days of answers (#388): the
Facebook/Instagram in-app browsers on iOS keep no `Partitioned` cookie, so every section POST failed CSRF,
and Chromium creators ended up with two `csrftoken` cookies (Django reads the last, `document.cookie`
readers the first). With the switch off the same middleware sweeps the stale partitioned pair from
browsers that still send it. A framed survey keeps its session through the cookie-less carrier below
instead — never turn the switch back on for embeds. The respondent page adds `MS-Embedded: 1` to its HTMX
calls when framed, which is how the final redirect stays on the in-frame thanks page (`?next=`) instead of
navigating the frame to `redirect_url`. The Share page hands out the snippet (`snippet_html`), `/oembed/`
describes it for platforms that do oEmbed discovery, and `/embed.js` (served by a view so the path never
changes) grows the host's iframe from the height messages the page posts. Safari and every iOS browser keep
no cookies inside a third-party frame, so `EmbedSessionMiddleware` (the project's SessionMiddleware) lets a
framed page carry its session key itself — `X-MS-Session` header, `ms_sid` form field with a same-host
Origin, one-time `ms_h` handoff on redirects — only under `/surveys/`, only without a session cookie, never
for a signed-in session, with CSRF still checked (the secret rides in the session). A new respondent view
needs nothing: the mark happens in access control and the carrier in middleware; a new full-page respondent
FORM needs `{% embed_session_field %}` next to its `{% csrf_token %}`.

**Session Management**: Survey sessions are created on first section view and tracked via `request.session['survey_session_id']`.

**Empty sessions (change `hide-empty-sessions`, issue #226)**: a session with no top-level `Answer`
(`parent_answer_id IS NULL`) is EMPTY — someone opened the survey and left (71% of external
sessions in Sept 2026). One definition, `analytics.nonempty_sessions(qs)` / `empty_sessions(qs)`;
the completion state, the v2 Responses page and `export.excluded_sessions` all go through it.
The v2 page hides empties unless the `rv2_show_empty` cookie is `1` (`analytics_views._show_empty`;
the legacy page and every other `SurveyAnalyticsService` caller keep `include_empty=True` and see
all sessions). `service.empty_count` feeds the "N opened without answering" line
(`editor/partials/_empty_sessions_toggle.html`). Response numbers `#N` come from
`service.sequence_numbers()` — rank among non-empty sessions; empty rows carry none — and
`comments.session_seq` follows the same rule. An empty row keeps its "Empty" badge and no marker. Exports
never contain empty sessions, whatever `include_all` says, and since `data-scope` neither does the
public results `response_count`; the funnel/Perf pane (`SurveyEvent`) still counts every session. The section POST treats
whitespace-only values as blank and stores text/number values stripped.

**Required questions unanswered / completed (`survey/required_state.py`, change
`responses-required-unanswered`, #691)**: ONE definition — a session's missing required questions
are the required top-level questions of ITS version that the visibility engine shows it (operator
surface for paper/operator sessions, respondent surface otherwise; `html`/`image` never; geo needs
`min_features`, `layer_objects` needs `min_objects` distinct objects; a blank row does not count).
*Completed* = not empty AND nothing missing — `analytics.completed_session_filter(qs)` =
`nonempty_sessions(qs).filter(required_complete=True)`, read by the Overview, the trend, the table's
Complete / Required unanswered chips (`?required=complete|missing`), the dashboard cards, the export's
`completed_only`, the REST summary and MCP (`SessionScope(completed=True)`). Reaching the last section
or the thanks page is NOT part of it. The result is STORED on the session (`required_missing` codes in
survey order, `required_complete`; both defaults agree) because counts run over thousands of sessions:
`required_state.refresh(session)` after every write of answers (`save_section_answers` — every answer
surface, forward and Back —, inline edit, paper supersede, ZIP import), and
`schedule_survey_refresh(header_id)` (on commit; inline up to `SYNC_LIMIT` non-empty sessions, else the
`recompute_required_state` task with an inline fallback) when an in-place edit changes the required set
(`services/questions.py::_required_set_changed`, create of a required question, delete). **A new path
that writes answers or changes what is required must call one of the two.** Publishing needs nothing:
old sessions move with their structure. The marker is quiet (`_required_unanswered_mark.html`: grey,
no count, tooltip names the questions); the one per-answer note left is crossed polygon edges
(`SurveyAnalyticsService.crossed_shapes`). The old Issues engine (duplicate by User-Agent, fast,
last-section "incomplete", outliers) and the survey validation-settings dialog are gone on purpose —
creators deleted real answers because of them; do not bring per-session "issues" back.
`SurveyHeader.validation_settings` is an unused column. Number questions' `min_value`/`max_value`
are enforced (input `min`/`max`, `views.number_value` drops an out-of-range POST; spec
`number-question-bounds`).
