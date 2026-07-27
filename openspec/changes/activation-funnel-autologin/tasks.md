# Tasks: activation-funnel-autologin

## 1. Auto-login + activation window

- [x] 1.1 `mapsurvey/settings.py`: `ACCOUNT_ACTIVATION_DAYS` from env, default 7
- [x] 1.2 `DirectActivationView`: on successful activation, `auth.login(request, user, backend='survey.backends.EmailOrUsernameBackend')` and redirect to `settings.LOGIN_REDIRECT_URL`
- [x] 1.3 `DirectActivationView`: valid key + already-active account → redirect to login (or `/editor/` if session already authenticated) instead of the failure page (mail-scanner sequence). **Deliberately does NOT sign them in** — see 1.5
- [x] 1.4 Tests (GIVEN/WHEN/THEN): valid key → active + authenticated session + redirect to `/editor/` + `last_login` set; expired key → failure page; valid key on already-active account → no failure page
- [x] 1.5 **Scope correction made during implementation.** The design originally allowed auto-login on the already-activated replay. Rejected once implemented: activation keys stay valid for the whole `ACCOUNT_ACTIVATION_DAYS` window, so signing in on replay would turn the emailed link into a 7-day reusable login credential (forwarded or leaked mail → account takeover). Auto-login now fires only on the inactive→active transition, which can succeed exactly once. design.md Risks updated; `test_replayed_key_does_not_sign_anyone_in` locks it in

## 2. Resend activation flow

- [x] 2.1 Open question resolved: reuse the existing `AbuseEvent.defense` choices (`ratelimit`, `honeypot`) and distinguish this endpoint via `detail` (`resend_hour`, `resend_day`, `resend_filled`). No new choice, no migration
- [x] 2.2 Settings: `RESEND_ACTIVATION_RATE_LIMIT_HOUR` (default 3, per IP), `RESEND_ACTIVATION_RATE_LIMIT_DAY` (default 3, per email), env-overridable
- [x] 2.3 `ResendActivationView` + `ResendActivationForm` (email + honeypot); POST always redirects to the neutral "check your inbox" page; email sent only for existing inactive accounts (case-insensitive match), fresh key via `get_activation_key`, existing activation templates
- [x] 2.4 Rate limiting per D3: per-IP (`ratelimit_key`) and per-email (`ratelimit_email_key`, new in `survey/abuse.py`), fail-open on cache outage, over-limit → `AbuseEvent` + neutral response (deliberately not 429 — a 429 would break the response uniformity that prevents enumeration)
- [x] 2.5 URL routes `/accounts/activate/resend/` + `/resend/done/`, ordered before the activation include; two new templates
- [x] 2.6 `activation_failed.html`: "Try registering again" replaced with a link to the resend form, copy mentions possible expiry
- [x] 2.7 Tests (GIVEN/WHEN/THEN): inactive → mail + neutral redirect; unknown / already-active / malformed email → no mail, identical response; honeypot → no mail + `AbuseEvent`; per-IP and per-email limits → capped + `AbuseEvent`; cache down → fail-open

## 3. Funnel dashboard stages

- [x] 3.1 `survey/funnel.py`: `_blank_row` gains `activated`, `logged_in`; `cohort_funnel()` reads `is_active`/`last_login` via `values_list` and increments; `alltime_totals()` sums the new keys
- [x] 3.2 `admin/funnel_dashboard.html`: Activated + Logged-in columns with percentages between Regs and Created; legend explains both gaps and their point-in-time semantics
- [x] 3.3 Tests (GIVEN/WHEN/THEN): active-never-logged-in counts in `activated` only; logged-in counts in both; inactive in neither; totals row sums; dashboard renders the columns

## 4. Verification

- [x] 4.1 Test suite: baseline **711 tests / 2 errors** → after **734 tests / same 2 errors**. +23 tests, no new failures. Both errors are pre-existing in `LastActivityMiddlewareTest` (unrelated `UserActivity` middleware)
- [x] 4.2 Flow coverage is automated rather than manual: the tests exercise real template rendering and redirects end to end (activation → `/editor/`; expired key → failure page carrying the resend link; resend → mail → key that activates; dashboard columns). **Not visually inspected in a browser** — worth a look before merge

## Notes for review

- Two test-harness details that were needed and are easy to regress:
  - Rate-limit tests must pin `CACHES` to LocMemCache. The configured Redis backend runs with `IGNORE_EXCEPTIONS`, so without Redis every counter silently no-ops and limit tests pass vacuously.
  - Activation mail is sent from a background thread (that is what keeps response time uniform and the endpoint non-enumerable), which makes `mail.outbox` assertions racy. `_InlineThread` runs the target synchronously in tests instead of removing the thread.
