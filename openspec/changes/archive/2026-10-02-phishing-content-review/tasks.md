## 1. Model, settings, audit

- [x] 1.1 Add `ContentReview` to `survey/models.py` (fields and index per spec `abuse-review`; `survey` FK to `SurveyHeader`, `decided_by` FK SET_NULL) and `('content_screen', 'Content screening')` to `AbuseEvent.DEFENSE_CHOICES`; migration `0091_contentreview`.
- [x] 1.2 Settings: `CONTENT_SCREENING` (bool env, default on), `CONTENT_SCREENING_HOLD_THRESHOLD` (int env, default 7), `ABUSE_REVIEW_EMAIL` (env, default `CONTACT_EMAIL`), `DISPOSABLE_EMAIL_DOMAINS` (comma env, default empty); document in `.env.example`.
- [x] 1.3 `survey/abuse.py`: add `log_abuse_event_noreq(defense, detail, ip=None, user_agent='')` sharing the write path with `log_abuse_event`.

## 2. Scorer (`survey/content_screening.py`)

- [x] 2.1 `collect_text(survey) -> ScreenInput` over name, section titles/subheadings (+translations), question names/subtexts (+translations), `thanks_html` (all languages), `redirect_url`, with account facts (age at now, email domain, question count); cap total text at 200 kB.
- [x] 2.2 `score(ScreenInput) -> ScreenResult` with the signal table from design D2: shortener hosts, click-tracker hosts, external links vs allow-list (`SITE_URL` host, `AWS_S3_CUSTOM_DOMAIN`, built-in safe hosts), brand terms, lure phrases, padding, ≤1 question, account age, disposable domain; weights in one dict; excerpts (≤120 chars) per signal.
- [x] 2.3 `fingerprint(ScreenInput)` = SHA-256 of normalised text.
- [x] 2.4 `screen_survey(survey, *, trigger)`: kill-switch check, fail-open wrapper, canonical anchoring, cleared-fingerprint skip, pending-row update instead of duplicate, hold → `ContentReview` + `AbuseEvent` + notice.
- [x] 2.5 Unit tests (GIVEN/WHEN/THEN): the XFINITY fixture ≥ threshold with the expected signals; the "PDF Document" + tracker `redirect_url` fixture ≥ threshold; the nine legitimate fixtures from the scan (own S3, Facebook, project site, retailer image, etc.) < threshold; age + one question alone < threshold; scorer exception does not raise from `screen_survey`.

## 3. Hooks

- [x] 3.1 `editor_survey_transition`: call `screen_survey(survey, trigger='publish')` after save when `new_status == 'published'`, inside the same never-block pattern as `scaffold_page`.
- [x] 3.2 `editor_publish_draft`: call `screen_survey(canonical, trigger='draft_publish')` after `publish_draft()` returns.
- [x] 3.3 `editor_survey_settings`, `editor_survey_settings_panel`, `editor_survey_thanks_panel`: after a successful save on a `published` survey call `screen_survey(survey, trigger='live_edit')`.
- [x] 3.4 Tests: publish of a lure creates one pending review and one `AbuseEvent`; second publish while pending creates nothing new; draft publish anchors the review to the canonical; live `redirect_url` edit re-screens; `testing` transition and draft saves do not screen; kill switch off → no review.

## 4. Hold gate and creator banner

- [x] 4.1 `access_control.check_survey_access`: for `published` surveys, if a `pending` review exists for `canonical_of(survey)` render `survey_unavailable.html` (200, neutral copy, `noindex`); keep owner/editor bypass.
- [x] 4.2 Template `survey/templates/survey_unavailable.html` modelled on `survey_closed.html`, i18n strings.
- [x] 4.3 Creator banner on `editor_survey_detail` (and the mobile nav header if it renders status) when a pending review exists: calm copy, no signals; add `pending_review` to the view context.
- [x] 4.4 Tests: anonymous respondent on entry and section URLs of a held survey gets the unavailable page and no `SurveySession`; owner still gets the survey; banner present with none of the signal words; reported-only survey serves normally.

## 5. Notification mail

- [x] 5.1 Celery task `send_abuse_review_notice(review_id)` in `survey/tasks.py` (bind, retries like `send_thread_notification`, `fail_silently=False`); builds context: survey, creator facts (username, email domain, joined, surveys, sessions), prior reviews, signals with excerpts or report reason, signed review URL via `absolute_url`.
- [x] 5.2 `content_screening.notify_owner(review)`: `.delay()` in try/except → synchronous `send_templated_mail(..., fail_silently=True)` on failure.
- [x] 5.3 Templates `survey/templates/abuse/review_notice.txt` (link in the first lines) and `.html`.
- [x] 5.4 Tests: one mail to `ABUSE_REVIEW_EMAIL` on hold with subject containing name and score, body containing link and signals; broker failure still sends; creator never receives mail.

## 6. Staff review page and decisions

- [x] 6.1 `survey/abuse_review_views.py`: `review_token(review)` / `review_from_token(token)` (`signing.dumps/loads`, salt `survey.abuse_review`, `max_age` 14 days); view `abuse_review` at `/editor/abuse-review/<token>/` — GET staff-only (404 otherwise), POST with `action=release|confirm`, CSRF.
- [x] 6.2 `content_screening.release(review, actor)` and `confirm_phishing(review, actor)` (deactivate, close `draft/testing/published` surveys with an audit row each, delete the user's sessions, `AbuseEvent`, review status); both no-ops on a decided review.
- [x] 6.3 Template `survey/templates/abuse/review.html` extending `editor_base.html`: evidence block, excerpts, account facts, prior reviews, two forms with the consequence written under each button; decided state read-only.
- [x] 6.4 URL entry in `survey/urls.py`.
- [x] 6.5 Tests: GET anonymous/non-staff → 404, nothing changes; bad/expired token → 404; release clears and the survey serves again with an `AbuseEvent`; confirm deactivates the user, closes their surveys with audit rows, kills sessions, writes the `confirm` event; decided review rejects further actions.

## 7. Admin

- [x] 7.1 Register `ContentReview` (list: status, survey, score, source, created_at, decided_at; filter status; readonly evidence; link to the review page) and `AbuseEvent` (read-only list, filter by defense) in `survey/admin.py`.
- [x] 7.2 Test: pending review appears in the admin changelist with the review link.

## 8. Respondent report

- [x] 8.1 Partial `survey/templates/partials/_abuse_footer.html` (safety notice + "Report this survey" link), included from `base_survey_template.html` and the thanks template next to `_made_with_mapsurvey.html`.
- [x] 8.2 View `survey_report` at `/surveys/<uuid>/report/` (GET form, POST create-or-increment `reported` review via `content_screening.report(survey, reason, message, request)`, `AbuseEvent`, notice on first report only, per-IP 3/hour limit with the registration cache helpers, neutral thank-you page); 404 for unknown/draft surveys through `resolve_survey` + `check_survey_access` semantics.
- [x] 8.3 Tests: notice and link on a section page and the thanks page; first report creates the row and sends one mail while the survey still serves; second report increments `report_count` and sends nothing; fourth report from one IP → 429; unknown/draft UUID → 404.

## 9. Documentation and wrap-up

- [x] 9.1 `CLAUDE.md`: a "Content screening (phishing)" paragraph — where the signals live, the hold model, the never-auto-ban rule, the kill switch and rollback.
- [x] 9.2 Run `./run_tests.sh survey` once before and once after; record the delta. (2026-10-02: 2247 tests OK, skipped=1, 33 new; origin/master baseline 2214 — no regressions.)
- [x] 9.3 Update GitHub issue #225 with the change link and what is deferred — PR #236 carries `Closes #225`; deferred items are listed in the proposal and in #225 itself.
