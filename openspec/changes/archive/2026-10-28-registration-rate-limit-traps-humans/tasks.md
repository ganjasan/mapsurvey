# Tasks

## 1. Settings and kill switch

- [x] 1.1 Add `REGISTRATION_INVALID_LIMIT_HOUR` (default 15), `REGISTRATION_INVALID_LIMIT_DAY` (default 50), and `REGISTRATION_SPLIT_RATE_LIMIT` (default `True`) to `mapsurvey/settings.py`.
- [x] 1.2 Declare the three variables in `render.yaml`, with the split switch dashboard-settable.
- [x] 1.3 Document them in `.env.example`.

## 2. Split the rate-limit check from the increment

- [x] 2.1 `check_registration_limit()` / `increment_registration_limit()` in `survey/abuse.py`, sharing `ratelimit_key` and the fail-open behaviour.
- [x] 2.2 `dispatch()` checks both counters without incrementing; logs the `AbuseEvent` and renders the 429 on a hit.
- [x] 2.3 `post()` increments the invalid counter when the form is invalid, the valid counter otherwise — before the Turnstile check.
- [x] 2.4 `REGISTRATION_SPLIT_RATE_LIMIT=False` increments the valid counter for every POST in `dispatch()`, reproducing the old behaviour.
- [x] 2.5 Honeypot path still returns fake success without touching either counter (covered by the existing `test_honeypot_short_circuits_turnstile`).
- [x] 2.6 **Off-by-one found during implementation**: the check must use `get_usage()` with `count >= limit`, not `is_ratelimited()` (`count > limit`). The latter is correct only when the same call increments; used read-only it lets through exactly one attempt more than configured.

## 3. The 429 page

- [x] 3.1 `survey/templates/registration/rate_limited.html` — what happened, when to retry, links to sign-in and password reset. No thresholds.
- [x] 3.2 Rendered with status 429 and the `Retry-After` header preserved.
- [x] 3.3 `TemplateCommentSyntaxTest` run right after editing templates — green.

## 4. Auth form presentation

- [x] 4.1 `registration/login.html` keeps the submitted username via an explicit `value`; the password is not repopulated.
- [x] 4.2 Sign-in failure message stays generic (does not reveal whether the account exists) and now links to resend-activation, the most common real cause it cannot name.
- [x] 4.3 Error styling strengthened. **Correction to the original diagnosis**: `.helptext` and `.errorlist` were already styled — inline in `base.html`, not in `main.css`, which is why the first grep missed them. They were too weak to read as errors (0.85rem red text, no surface, no icon), not absent. Errors now carry a background, a left border, and a `⚠` marker.
- [x] 4.4 Django's stock username help text replaced; the "150 characters or fewer" ceiling is gone. Password help text removed in favour of the checklist.
- [x] 4.5 **Wrong template found during implementation**: the live page is `django_registration/registration_form.html`; `registration/registration_form.html` is dead and was reverted.

## 5. Password rules: enforced vs advisory

- [x] 5.1 `survey/password_rules.py` derives enforced rules from `AUTH_PASSWORD_VALIDATORS` and adds advisory entries for validators that are not configured.
- [x] 5.2 `AUTH_PASSWORD_VALIDATORS` reduced to `MinimumLengthValidator` (decision 2026-08-17). Common passwords, email/username reuse and all-numeric passwords now warn instead of blocking. Divergence from NIST SP 800-63B recorded in the settings comment and the proposal.
- [x] 5.3 `survey/assets/js/password-checklist.js` ticks rules off as the user types; advisory misses render amber with `⚠`, never as red errors. Never blocks submission.
- [x] 5.4 Degrades with JS off to a plain list of the rules; `collectstatic` run.

## 6. Tests

- [x] 6.1 **Original task was wrong**: no existing test asserted that a form-invalid POST increments the counter — they all posted *valid* data, which is why the defect shipped green. Nothing to rewrite; the gap was coverage, not a bad assertion.
- [x] 6.2 Three form-invalid POSTs then a valid one → `User` created, no 429.
- [x] 6.3 Invalid-attempt ceiling → 429 with `AbuseEvent(detail='invalid_hour')`.
- [x] 6.4 Turnstile failure consumes the strict budget, not the loose one.
- [x] 6.5 429 is HTML, has `Retry-After`, links to sign-in and reset, leaks no thresholds.
- [x] 6.6 Failed sign-in keeps the username, clears the password.
- [x] 6.7 Canary: a configured validator with no checklist entry fails the suite.
- [x] 6.8 Kill switch restores the old counting.
- [x] 6.9 Redis outage still fails open (new test patching both helpers).
- [x] 6.10 Common password, and a password matching the email, are both accepted; a 7-character password is still rejected.
- [x] 6.11 Sign-in failure message identical for existing and non-existing accounts.
- [x] 6.12 Baseline `./run_tests.sh survey` = 1322 tests OK; after = 1338 tests OK (16 added, none broken).

## 7. Post-deploy verification

- [ ] 7.1 After merge, complete a real registration end-to-end on production.
- [ ] 7.2 Check `AbuseEvent` rows with `detail='invalid_hour'` over the first day.
- [ ] 7.3 Confirm `creator_registered` fires in PostHog for that registration.
