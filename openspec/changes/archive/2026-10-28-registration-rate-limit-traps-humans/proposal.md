## Why

On 2026-08-17 a visitor arrived from `/alternatives/maptionnaire/`, opened `/accounts/register/`, and
never got an account. Render request logs show six POSTs from `31.209.215.222`: three returned 200
(form re-rendered with validation errors), then three returned 429. PostHog recorded 23 `$dead_click`
events across the same session, one of them landing exactly on the string "Your password can't be too
similar to your other personal information." No `creator_registered` event fired; the last one in the
project is from 2026-08-12.

Three independent defects compounded into a total loss of a qualified, competitor-comparing lead:

1. The per-IP rate limit counts **every** POST, including ones rejected by form validation. Three
   password typos exhaust the hourly budget (`REGISTRATION_RATE_LIMIT_HOUR = 3`) and lock a legitimate
   human out for an hour. The defense was designed against bots and is instead hitting people who are
   demonstrably trying to give us their email.
2. The 429 response is `text/plain` with a single English sentence and no markup, navigation, or link
   back. To the user it reads as a broken site, not as "wait an hour."
3. Validation errors and password requirements render as unstyled default `<ul>` lists — `.helptext`
   has no CSS at all and `.errorlist` is styled only inside `.question-card`, which does not apply on
   auth pages. The dead clicks are the measurable symptom: the user was clicking on error text because
   nothing marked it as an error.

We cannot contact the affected people. `AbuseEvent` deliberately stores no email or username (GDPR),
no `User` row is created on a 429, and request logs carry only IP and user agent. Every user lost this
way is lost silently and permanently — which is also why the loss is invisible in the funnel dashboard.

A fourth, related defect surfaced during the investigation: the sign-in page discards the entered
username on a failed attempt, because `registration/login.html` renders raw `<input>` elements with no
`value` instead of the bound form fields. Registration itself does not have this problem.

## What Changes

- Rate limiting on registration counts only POSTs that pass form validation. A submission rejected by
  the form (password too weak, passwords mismatched, username taken, email malformed) no longer
  consumes the budget. Bot-shaped traffic is unaffected: honeypot and Turnstile still fire first and
  still count, and a bot posting valid-but-fake data is still limited exactly as before.
- A separate, looser ceiling bounds invalid attempts so the endpoint cannot be used as an unmetered
  password-validator oracle or a CPU sink: `REGISTRATION_INVALID_LIMIT_HOUR = 15` and
  `REGISTRATION_INVALID_LIMIT_DAY = 50`, counted independently of the valid-POST limits, which stay
  at 3/hour and 10/day.
- The 429 response becomes a rendered HTML page in the site's layout, stating in plain language what
  happened, when the user may retry, and offering links to sign in and to password reset. The
  `Retry-After` header is preserved.
- `.helptext` and `.errorlist` get visible styling on auth pages, so password requirements read as
  requirements and validation failures read as failures.
- The password field gains a live requirement checklist that updates as the user types, so a weak
  password is caught before the submit rather than after it. This is a convenience layer only —
  server-side validation stays the sole authority, and the page must remain fully usable with JS
  disabled (the checklist degrades to a plain list of the rules).
- Password composition stops blocking registration. `AUTH_PASSWORD_VALIDATORS` keeps only
  `MinimumLengthValidator`; common passwords, reuse of the email/username, and all-numeric passwords
  become advisory checklist entries that warn but accept. The person lost on 2026-08-17 was rejected
  by `UserAttributeSimilarityValidator`, which is Django's `SequenceMatcher` at 0.7 against the user's
  attributes — not what NIST SP 800-63B actually asks for, and the most false-positive-prone of the
  four. **This is a deliberate divergence from NIST SP 800-63B**, which states the compromised-password
  check as a SHALL: a security questionnaire asking whether we reject known-breached passwords now
  gets "no, we warn". Accepted knowingly; re-adding `CommonPasswordValidator` is a one-line change and
  the checklist follows it automatically.
- The sign-in form preserves the entered username after a failed attempt and clears only the password.
- Field help text on the registration form is rewritten for humans. Django's stock username help text —
  "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only." — states a ceiling nobody
  will ever reach while saying nothing about what actually blocks a submission. Help text SHALL state
  the constraint a user can realistically violate (minimum length, allowed characters), not the
  theoretical maximum.

## Capabilities

### New Capabilities

- `auth-form-feedback`: how authentication and registration forms present validation errors, field
  help text, and rate-limit refusals to the user, and which entered values survive a failed
  submission.

### Modified Capabilities

- `registration-abuse-defenses`: the "Per-IP rate limiting on registration POST" requirement changes
  from counting every POST to counting only POSTs that pass form validation, with a separate ceiling
  for invalid attempts; the 429 response changes from `text/plain` to a rendered HTML page while
  keeping its status code and `Retry-After` header.

## Impact

- `survey/views.py` — `AbuseProtectedRegistrationView.dispatch()` (rate-limit check moves out of
  `dispatch`, since it must run after form validation) and `post()` (ordering of the defenses).
- `survey/abuse.py` — rate-limit helpers; possibly a second limit group for invalid attempts.
- `survey/templates/registration/login.html` — bound form fields instead of raw inputs.
- New template for the 429 page.
- `survey/assets/css/main.css` — auth-page error and help-text styling (edit in `assets/`, then
  `collectstatic`).
- `survey/tests.py` — `RegistrationAbuseTest` and neighbours; the existing scenarios asserting that
  any POST increments the counter will need updating, and they are the reason this defect shipped
  green.
- No model or migration changes. `AbuseEvent` keeps its current fields and its no-PII guarantee.
- Behavioural change visible in production within minutes of merge (no staging gate), so the rate-limit
  change ships behind an env-var kill switch.
