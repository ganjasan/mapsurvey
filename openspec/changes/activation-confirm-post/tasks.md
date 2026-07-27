# Tasks: activation-confirm-post

## 1. View split

- [x] 1.1 `DirectActivationView.get()`: validate key via `ActivationForm`; expired/invalid → failure page; already-active → login redirect (unchanged); valid+inactive → render `activation_confirm.html` with the key. No writes on GET
- [x] 1.2 `DirectActivationView.post()`: re-validate key from form body; activate + auto-login + redirect `/editor/`; `already_activated` → login redirect without sign-in; expired/invalid → failure page

## 2. Template

- [x] 2.1 `django_registration/activation_confirm.html`: auth-card, one-button CSRF form with hidden `activation_key`, copy explaining the click confirms the email and signs in. No JS auto-submit (D1 alternative rejected — JS-executing scanners would submit it)

## 3. Tests

- [x] 3.1 Rework `ActivationAutoLoginTest` for the GET/POST split: GET valid key → 200 confirm page, account still inactive, no session; POST → active + session + `/editor/` + `last_login`
- [x] 3.2 New scanner scenarios: GET and HEAD on a valid link leave the account inactive; POST replay on an active account creates no session
- [x] 3.3 Keep: expired/missing/unknown-username key behavior, already-active GET → login redirect, resend flow tests (untouched)

## 4. Verification

- [x] 4.1 Full `./run_tests.sh survey`; compare to the 734/2-pre-existing-errors baseline

## Result

- Suite: 734 → 737 tests, same 2 pre-existing `LastActivityMiddlewareTest` errors, no new failures.
- Task 4.1 note: net +3 tests (confirm-page GET, scanner GET/HEAD, expired-key POST); one replay test reshaped from GET to POST semantics.
