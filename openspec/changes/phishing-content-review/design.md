## Context

Registration is defended (honeypot, per-IP rate limit, Turnstile — `survey/abuse.py`, spec `registration-abuse-defenses`), but the first thing a creator publishes is never inspected. Two phishing surveys were found by a one-off scan on 2026-10-02 (issue #225); both were cleaned up in a Django shell because nothing in the product can hold a survey, notify the owner, or deactivate an account with its surveys.

Current state that shapes the design:

- Content goes live in exactly two places: `editor_survey_transition` (`survey/editor_views.py:2442`) and `editor_publish_draft` → `versioning.publish_draft`. Question and section text is locked on a published survey (`_check_structural_edit_allowed`), but `redirect_url` (`editor_survey_settings`, `editor_survey_settings_panel`) and `thanks_html` (`editor_survey_thanks_panel`) stay editable live — the "PDF Document" lure kept its payload in `redirect_url`.
- Respondent access is centralised in `access_control.check_survey_access`; `closed` already renders a neutral `survey_closed.html`.
- Mail: `survey/mail.py::send_templated_mail` + one Celery task per recipient (`survey/tasks.py`), `SITE_URL` for links. No `ADMINS`; the closest owner address is `CONTACT_EMAIL`.
- `AbuseEvent` is the audit table (no FK to user or survey by design — GDPR); `log_abuse_event` needs a request.
- Signed values use `signing.dumps/loads` with a salt and `max_age` (`survey/events.py`). No `TimestampSigner`.
- Kill switches are `os.environ.get('NAME', 'True').lower() in ('true','1')`.
- Owner's rule: **nothing bans automatically** — the owner gets a system email and confirms.
- Owner's decision (2026-10-02): a flagged survey is **held until the decision** (Microsoft Forms model), not published-and-notified.

How others do it: Microsoft Forms temporarily blocks responses on a flagged form and lets an admin "Unblock" or "Confirm phishing" from a notification; Jotform auto-suspends accounts on field-label matches (many false positives on their forum); Google Forms blocks password-like fields and prints "Never submit passwords" + "Report abuse" under every form. Google Safe Browsing is non-commercial-only; Web Risk (100k lookups/month free) is the commercial path — deferred.

## Goals / Non-Goals

**Goals:**
- Stop a lure from serving to respondents between publish and the owner's decision.
- Put the decision in the owner's hands with the evidence in the email and two explicit actions.
- Make the ban a single, audited, reversible-by-admin action that covers the whole account.
- Keep honest creators moving: scoring that fails open, a threshold calibrated so none of the 580 legitimate surveys in the 2026-10-02 scan would have been held, and a calm "under review" message instead of an accusation.
- One module owns the signals so a new incident is a row in a list, not a new code path.

**Non-Goals:**
- Automatic bans of any kind.
- External URL-reputation lookups (Web Risk), disposable-domain blocking at registration, a periodic re-scan, Discord pings — all noted in #225 as follow-ups.
- Screening `testing` surveys (their audience is the creator's own testers) or drafts.
- A general-purpose moderation queue UI; the review page serves one review, the admin lists the rest.

## Decisions

**D1. A `ContentReview` row, not a sixth survey status.**
Adding `held` to `STATUS_CHOICES` would touch `VALID_TRANSITIONS`, every status badge, the lifecycle UI, analytics scopes and the indexing flag. Instead the survey gets its `published` status as today and a `ContentReview(status='pending')` row anchored to the canonical survey; `check_survey_access` consults it for published surveys and renders the hold page. Release is then a row update, not a status transition, and the kill-switch rollback leaves the lifecycle untouched.
*Alternative rejected:* `held` status — invasive; `is_held` boolean on `SurveyHeader` — loses the evidence and the decision record.

**D2. The scorer is a pure function in `survey/content_screening.py`.**
`collect_text(survey) -> ScreenInput` gathers survey name, section titles/subheadings, question names/subtexts (translations included), `thanks_html` (every language), `redirect_url`, plus account facts (age at publish, email domain, question count). `score(ScreenInput) -> ScreenResult(score, signals)` is deterministic, has no DB or network access, and is what the unit tests exercise against the two incidents and the nine false-positive candidates from the scan. `screen_survey(survey, *, trigger)` is the only entry point views call; it wraps everything in `try/except Exception: logger.exception(...); return None` — fail open.

Signals and default weights (calibrated on the 2026-10-02 scan; hold threshold `CONTENT_SCREENING_HOLD_THRESHOLD` default 7):

| signal | weight | note |
|---|---|---|
| URL-shortener host (bit.ly, tinyurl, t.co, cutt.ly, is.gd, rb.gy, t.ly, s.id, rebrand.ly, `go.*` under an unknown apex, …) | 4 each, cap 8 | strongest single signal |
| email click-tracker host (`*.zohoinsights.com`, `click.`, `trk.`, `sender\d+.`, `/ck1/`-style paths) | 2 | the "PDF Document" case |
| any external link (host not allow-listed) | 2 once | allow-list: `SITE_URL` host, `AWS_S3_CUSTOM_DOMAIN`, mapsurvey.org, google.*, youtube/youtu.be, vimeo, wikipedia, openstreetmap, `.gov`, `.edu`, `.ac.*` |
| impersonated brand term (xfinity, comcast, microsoft, office 365, outlook, sharepoint, onedrive, docusign, dropbox, paypal, wells fargo, chase, bank of america, apple id, netflix, amazon prime, usps, fedex, dhl, irs, hmrc …) | 2 each, cap 4 | word-boundary, case-insensitive |
| lure phrase (click here, proceed, verify your, sign in, log in, password, mailbox, almost set, account suspended, pdf document, secure message, shared a file…) | 1 each, cap 4 | |
| padding: ≥ 20 empty paragraphs (`<p><br></p>`, `<p></p>`, `&nbsp;`-only) | 3 | |
| at most one question in the whole survey | 1 | |
| account age at publish < 1 h | 2; < 24 h → 1 | AI-generated first surveys are often minutes old — never enough alone |
| disposable email domain (small built-in list + `DISPOSABLE_EMAIL_DOMAINS` env) | 2 | |

Scores from the scan: incident 1 → 19, incident 2 → 8, highest legitimate → 5. Weights live in one dict; tests pin the two incidents above threshold and the legitimate set below.

**D3. Where screening runs.**
- `editor_survey_transition` when `new_status == 'published'`: after `survey.save()`, before the HTMX response. Same "must never block" shape as `scaffold_page`.
- `editor_publish_draft`: after `publish_draft()` returns, on the canonical survey (the draft's content now lives there).
- `editor_survey_settings`, `editor_survey_settings_panel`, `editor_survey_thanks_panel`: after a successful save when `survey.status == 'published'` — these are the only live-editable text fields.
Trigger name (`publish`, `draft_publish`, `live_edit`) is stored on the review.
*Alternative rejected:* a `post_save` signal on `SurveyHeader` — fires on every unrelated save and cannot see the trigger.

**D4. Content fingerprint prevents re-holding what the owner already released.**
`fingerprint = sha256(normalised ScreenInput text)`. A survey with a `cleared` review for the current fingerprint is not held again; any text change (including `redirect_url`) changes the fingerprint and re-screens. A `confirmed` review is terminal — the account is inactive. At most one `pending` review per survey: a second trigger while pending updates `signals`/`score` on the existing row instead of creating a second mail.

**D5. Hold = respondents see `survey_unavailable.html`, creator sees a banner.**
`check_survey_access` for `published` surveys checks `ContentReview.objects.filter(survey=canonical, status='pending').exists()` (one indexed query; editors/owners still bypass as today, so the creator can open their own survey — the banner tells them why nobody else can). The hold page is the existing `survey_unavailable.html` served with 404 — exactly what an unknown UUID or a draft gets — so a held lure is indistinguishable from a dead link (which also keeps link scanners and crawlers off it); no reason, no survey name, `noindex`. The creator banner on `editor_survey_detail` says the survey is being reviewed, usually within a day, and respondents will see it once review completes. It lists no signals — explaining the heuristics to the person who tripped them is how Jotform's filter got mapped.

**D6. Owner email with a signed link to a staff-only review page; decisions are POSTs.**
Mail link scanners (Outlook Safe Links, Gmail) fetch URLs in incoming mail, so a GET must never ban anyone. The link is `/editor/abuse-review/<token>/` where `token = signing.dumps({'r': review.id}, salt='survey.abuse_review')`, `max_age` 14 days; the view requires `request.user.is_staff` (404 otherwise, like story previews) and renders the evidence: score, triggered signals with excerpts, survey name and link, creator username, email domain, registration time, surveys and sessions count, prior reviews for this account. Two forms: **Release** → `status='cleared'`, `decided_by/at`; **Confirm phishing** → `confirm_phishing(review, actor)`:
1. `user.is_active = False`
2. every `SurveyHeader` with `created_by=user` and status in (`draft`,`testing`,`published`) → `closed` (audit row per survey)
3. every session row whose `_auth_user_id` is the user → deleted
4. `AbuseEvent(defense='content_screen', detail='confirm survey=<id> user=<id>')`
5. review `status='confirmed'`.
The page shows the consequence under each button. Expired/invalid token → 404. An already-decided review renders read-only with the decision.
*Alternative rejected:* actions as Django admin actions only — fine as a fallback (and the admin registration is kept), but the owner reads mail on a phone and the one-click path matters.

**D7. Mail goes through Celery with a synchronous fallback.**
`send_abuse_review_notice(review_id)` is a `shared_task` like `send_thread_notification` (retries, `fail_silently=False`, PostHog on failure). The view calls `.delay()` inside `try/except Exception`: if the broker is unreachable the task is sent inline with `fail_silently=True` — a held survey with no mail is the one state this feature must not produce. Recipient: `settings.ABUSE_REVIEW_EMAIL` (env, default `CONTACT_EMAIL`). Subject: `[Mapsurvey] Survey held for review: <name> (score N)`. Templates `survey/templates/abuse/review_notice.{txt,html}` with the same evidence as the page plus the link; the plain-text part is what a phone mail client shows first, so it leads with the link.

**D8. Respondent report → review without a hold.**
A footer line in `_made_with_mapsurvey.html`'s neighbour partial `_abuse_footer.html` (included from `base_survey_template.html` and the thanks page): "Never enter passwords or card numbers in a Mapsurvey survey · Report this survey". `/surveys/<uuid>/report/` renders a small form (reason: phishing / scam / other, optional text ≤ 500 chars) and on POST creates `ContentReview(source='report', status='reported')` — **not** `pending`: a report must not let anyone take a competitor's survey offline. Repeated reports on the same survey bump `report_count` on the open row instead of mailing again. Per-IP limit 3/hour via the cache, same helpers as registration (fail open). The owner's review page offers the same Release (here: dismiss) / Confirm actions.

**D9. Audit without PII in `AbuseEvent`.**
`DEFENSE_CHOICES` gains `('content_screen', 'Content screening')`. `detail` carries `hold survey=<id> score=<n>`, `release survey=<id>`, `confirm survey=<id> user=<id>`, `report survey=<id>` — ids, never email or username, matching the model's docstring. `log_abuse_event` gets a request-less sibling `log_abuse_event_noreq(defense, detail, ip=None, ua='')` for the Celery/decision paths.

**D10. Kill switch semantics.**
`CONTENT_SCREENING=False` makes `screen_survey` return `None` before collecting text, hides the creator banner only when no pending review exists, and leaves the hold gate, review page, admin and report flow working — an in-flight hold is resolved by the owner, never silently opened by a flag flip. Rollback story: set the flag off, release any pending rows from the admin.

## Risks / Trade-offs

- [False positive holds a real creator for hours] → threshold calibrated above every legitimate survey in the scan; age and ≤1-question signals cannot hold alone; banner promises "usually within a day"; `ABUSE_REVIEW_EMAIL` is the owner's monitored address; release is one click. A held creator can still edit everything.
- [Attacker publishes clean content, gets released, then edits `redirect_url`] → fingerprint changes → re-screened on the live-edit hook.
- [Attacker learns the signals] → the creator-facing message carries no reasons; the weights are server-side only.
- [Broker down → no mail → survey held indefinitely] → synchronous fallback send; admin list of pending reviews.
- [Mail scanner prefetches the review link] → GET is read-only and staff-gated; decisions are POST with CSRF.
- [`confirm_phishing` closes a legitimate survey of a mis-judged user] → owner-confirmed only; reversible from the admin (`is_active`, statuses); audit rows name every survey touched.
- [Scorer regex cost on a 10-language survey with long subtexts] → text is capped at 200 kB per survey before scoring; runs once per publish, not per request.
- [Report flow abused to spam the owner] → no hold on reports, one open row per survey, per-IP limit.
- [Hold query on every respondent page] → one `exists()` on an indexed `(survey_id, status)` pair, published surveys only.

## Migration Plan

1. Migration 0091: `ContentReview` table + index; `AbuseEvent.defense` choices (no column change).
2. Deploy with `CONTENT_SCREENING` unset (= on). No backfill: existing published surveys are screened on their next publish or live edit only.
3. Set `ABUSE_REVIEW_EMAIL` in Render env (defaults to `CONTACT_EMAIL`, which is the owner's address today).
4. Rollback: `CONTENT_SCREENING=False`; release pending rows in `/admin/survey/contentreview/`. The migration is additive and stays.

## Open Questions

- Whether `testing` → `published` with `clear_test_data` should also drop a stale `cleared` review — leaning no: a cleared fingerprint is about content, not sessions.
- The disposable-domain list: ship ~40 well-known domains inline now, promote to a DB-backed list in the registration follow-up.
