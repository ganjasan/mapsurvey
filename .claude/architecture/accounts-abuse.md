# Accounts and abuse: registration, grace period, invitations, content screening, terms

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Registration abuse prevention**: `/accounts/register/` is served by `AbuseProtectedRegistrationView` (subclass of `AsyncEmailRegistrationView`). Two defenses run in order: honeypot field `website` (silent fake-success redirect), per-IP rate limit (`django-ratelimit`, fail-open on Redis outage). Cloudflare Turnstile was removed (#490) after it had been off in production; do not bring a CAPTCHA back without the owner — what an unconfirmed account can do is bounded by the grace period below. Helpers in `survey/abuse.py`. Audit log in `AbuseEvent` model. Real client IP via `survey.middleware.CloudflareIPMiddleware` reading `CF-Connecting-IP` only when `CLOUDFLARE_TRUSTED=True`.

**Sign-in grace period (change `login-grace-period`, #487)**: registration creates the account
ACTIVE and signs it in; `EmailVerification` (one row per account, no row = confirmed) records the
email confirmation, and `User.is_active=False` means ONLY a ban (`confirm_phishing`). The one rule
is `survey/email_verification.py` (`is_verified`, `grace_deadline` = `date_joined` +
`SIGN_IN_GRACE_HOURS` (24), `can_sign_in`, `awaits_confirmation`, `confirmed_q`, `send_link`):
never read `is_active` as "activated" and never compute the deadline elsewhere. Unconfirmed
accounts build freely for 24 h, but `services/publishing` refuses to publish (`EmailUnconfirmed`
→ editor 403 + dialog, REST/MCP `403 email_unconfirmed`) and `org_send_invitation` refuses to
invite; email-matched invitations are accepted on CONFIRMATION (`user_activated`), not at
registration. Past the deadline the backend refuses the password, `SignInForm` names the reason
to whoever typed the CORRECT password and sends a link (per-address daily cap shared by every
send), and `GracePeriodMiddleware` ends a grace session at its next request. There is no standing
confirm-email banner (removed in change `onboarding-friction`, #638 — it pulled new creators off
onboarding): `editor/partials/_confirm_email_banner.html` (both bases) now holds only the
"Confirm your email to publish" dialog and its resend script; do not bring a banner back. Newsletter and funnel
"activated" use `confirmed_q()`. After a deploy that touches accounts, run
`manage.py sync_email_verification` (idempotent) for rows the old instance created.

**Workspace invitations (change `invite-landing-journey`, #512)**: `survey/invitations.py` is the ONE
place an `Invitation` is accepted — `accept()` writes the membership (an existing member keeps their
role), `accepted_at`, the active workspace and a one-shot "just joined" mark in the session, and
emits `invitation_accepted` (org id, role, `surface` ∈ `link|register|sign_in|confirm`). The signed-in
accept view, `ActiveOrgMiddleware` (token parked by the landing page), the registration receiver and
the confirmation-time address match (`join_by_address`, rule of #487 unchanged) all call it; never
write `Membership` from an invitation elsewhere. **A registration that carries an acceptable
invitation gets NO personal workspace** (owner decision 2026-10-31): `create_personal_org_on_registration`
asks `accept_pending()` first and returns when it joined; a dead token falls through to the personal
workspace so no account is left without one. The landing page's two actions carry the token
(`/accounts/register/?invite=<token>`, `/accounts/login/?next=<accept URL>`), and the register page
pre-fills the invited address. The dashboard pops the mark once (`take_joined`): that render shows the
"You've joined" banner and never redirects to the start page; `editor_sees_none` is the editor's empty
state in a workspace that has surveys. `DirectActivationView.post` signs in BEFORE sending
`user_activated`, because `login()` flushes a session another account held.

**Content screening (phishing hold, change `phishing-content-review`)**: registration defenses stop
bots; `survey/content_screening.py` is for the human who publishes an "XFINITY — click here" page on
our domain. `screen_survey(survey, trigger=…)` runs at the moments creator text goes live —
`editor_survey_transition` to `published`, `editor_publish_draft` (on the CANONICAL survey) and the
live saves of `redirect_url`/`thanks_html` and, since `edit-live-survey`, of question and section
text on a published survey (all through `_rescreen_if_live`) — and NOWHERE else: drafts and
`testing` are not screened. `collect_text()` gathers name, section/question text with translations,
thanks page and `redirect_url`; `score()` is pure (no DB, no network) over the signal table at the top of
the module (`WEIGHTS`, shorteners, trackers, brand terms, lure phrases, padding, ≤1 question, account
age, disposable domain) — a new incident is a row there, never a new code path. At or above
`CONTENT_SCREENING_HOLD_THRESHOLD` (7, calibrated on the 2026-10-02 scan: incidents 19 and 8, best
legitimate 5) the survey keeps `status='published'` but gets a `ContentReview(status='pending')`;
`check_survey_access` then serves the same 404 `survey_unavailable.html` an unknown UUID gets, the
creator sees a calm banner with NO reasons, and `ABUSE_REVIEW_EMAIL` (default `CONTACT_EMAIL`) gets one
mail with a signed link to `/editor/abuse-review/<token>/`. **Nothing bans automatically**: the staff-only
page's Release / Confirm phishing are POSTs (mail scanners prefetch GETs), and `confirm_phishing` is the
one place that deactivates an account, closes its surveys (audit rows), kills its sessions. A `cleared`
review remembers the content `fingerprint`, so a released survey is re-screened only when its text
changes. Screening fails OPEN (any exception → logged, publish completes), the notice falls back to a
synchronous send if the broker refuses the task, and `CONTENT_SCREENING=False` stops new holds without
releasing existing ones (that is the owner's click, or the admin). Respondent pages carry the
`_abuse_footer.html` notice + `/surveys/<uuid>/report/`; a report opens a `reported` review that holds
nothing. Every hold/release/confirm/report writes an `AbuseEvent(defense='content_screen')` with ids only.

**Terms, privacy and ownership (change `dpga-readiness`)**: `/terms/` (`views.terms_page`,
`terms.html`) is the Terms of use plus the Acceptable use & safety policy; `/privacy/` is a 301 to
`/trust/`, which carries the `#ownership` block (owner: Artem Koniukhov). The Digital Public Goods
Alliance application links these pages as evidence, so the section ids on `/terms/` (`terms`,
`acceptable-use`, `prohibited`, `moderation`, `harassment`, `children`, `personal-data`, `contact`)
and `/trust/#ownership` must not be renamed, and every sentence there must stay true in production —
change the policy text when the behaviour changes. Bump `TERMS_UPDATED` in `views.py` whenever the
text of `terms.html` changes. Sign-up requires `accept_terms` (16+, self-declared, nothing stored).
Report reasons live in `content_screening.REPORT_REASONS`; a `child_abuse` report always mails the
moderator with an `[URGENT]` subject, even on a survey that already has an open review.
