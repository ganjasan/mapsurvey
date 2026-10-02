## Why

On 2026-10-01 a creator registered from a disposable-mail domain and, two minutes later, published a survey whose only content was an "XFINITY — click here to proceed" lure pointing at a URL shortener, padded with 74 empty paragraphs so the dummy question sat below the fold. A second case (a "PDF Document" survey whose payload was the `redirect_url`) had been sitting in draft since August. Registration defenses stop bots, not a human with a throwaway mailbox; nothing looks at what a survey *says* before it goes live on `mapsurvey.org/surveys/<uuid>/`. One mass-mailed lure puts the whole domain on Safe Browsing / Spamhaus lists, which breaks every customer's survey and our transactional mail at once. Both incidents were found by hand and cleaned up in a Django shell (GitHub issue #225).

## What Changes

- **Content screening at publish time.** When a survey is published (status transition or draft publish) and when `redirect_url` / `thanks_html` are saved on an already-published survey, the system scores the creator-authored text (section subheadings, question names and subtexts, thanks page, redirect URL, survey name) for phishing signals: external links and URL shorteners, lure vocabulary and impersonated brands, empty-paragraph padding, a survey with at most one question, an account that is minutes old, a disposable-mail domain. The scorer is pure, deterministic, allow-lists our own hosts, and fails OPEN — a scorer error never blocks a creator.
- **Held for review, never auto-banned.** A survey whose score reaches the hold threshold still gets its `published` status, but respondents see a neutral "this survey is not available" page and the creator sees a calm "under review, usually within a day" banner until the owner decides. Nothing is done to the account automatically.
- **Owner review by email.** The site owner (`ABUSE_REVIEW_EMAIL`, default `CONTACT_EMAIL`) receives one email per held survey with the triggered signals, text excerpts, account facts, and a signed link to a staff-only review page with two actions: **Release** (survey serves again, this content fingerprint is remembered as cleared) and **Confirm phishing** (account deactivated, every survey of that account closed, login sessions killed). Both are POST actions behind a staff login, so mail link-scanners that prefetch URLs cannot trigger them. A cleared survey is re-screened only if its content changes.
- **Audit trail.** Every hold and every decision writes an `AbuseEvent` with a new defense slug `content_screen`; the review row records who decided and when. Held reviews are listed in the Django admin for the case where mail is lost.
- **Respondent-side report link.** Every respondent survey page carries a footer line "Never enter passwords or card numbers in a Mapsurvey survey" and a "Report this survey" link; a report creates a pending review for the survey (rate-limited per IP) and goes through the same owner-review flow.
- **Kill switch.** `CONTENT_SCREENING` (default on) disables scoring and holding; the review page, admin listing and report link keep working so an existing hold can still be resolved.

Out of scope (tracked in #225 as follow-ups): a disposable-domain blocklist at registration, Safe Browsing / Web Risk URL lookups, a periodic re-scan of all published surveys, Discord notifications.

## Capabilities

### New Capabilities
- `survey-content-screening`: the scoring function, its signals and weights, when it runs (publish, draft publish, live edits of redirect/thanks), the hold threshold, fail-open behaviour, the kill switch.
- `abuse-review`: the `ContentReview` record, the held state as seen by respondents and the creator, the owner notification mail, the staff review page with Release / Confirm phishing, the effects of each decision, the content-fingerprint rule for re-screening.
- `respondent-abuse-report`: the respondent-page footer notice and the "Report this survey" flow that opens a review.

### Modified Capabilities
- `abuse-event-log`: the `defense` slug set gains `content_screen`; rows written on hold, release, confirm and respondent report, with the survey id in `detail`.

## Impact

- **Models / migration 0091**: new `ContentReview` (survey FK, status, score, signals JSON, content fingerprint, source, decided_by, decided_at); `AbuseEvent.DEFENSE_CHOICES` gains `content_screen`.
- **New module** `survey/content_screening.py` (scorer, fingerprint, hold/decide helpers) — the one place the signals live.
- **Hooks** in `survey/editor_views.py` (`editor_survey_transition`, `editor_publish_draft`, `editor_survey_settings_panel`, `editor_survey_settings`, `editor_survey_thanks_panel`) and in `survey/versioning.py::publish_draft` callers.
- **Respondent gate** in the survey entry/section views (`survey/views.py`) and a new placeholder template; footer partial in `base_survey_template.html`.
- **New views** `survey/abuse_review_views.py` (review page, decisions, respondent report), URLs under `/editor/abuse-review/<token>/` and `/surveys/<uuid>/report/`.
- **Mail**: Celery task in `survey/tasks.py` through `send_templated_mail`, templates `survey/templates/abuse/review_notice.{txt,html}`; new settings `ABUSE_REVIEW_EMAIL`, `CONTENT_SCREENING`, `CONTENT_SCREENING_HOLD_THRESHOLD`.
- **Admin**: `ContentReview` and `AbuseEvent` registered read-mostly in `survey/admin.py`.
- **Creator UI**: an "under review" banner on the editor survey page.
- No external services, no new dependencies.
