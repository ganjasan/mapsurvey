## 1. Model and the one rule

- [x] 1.1 `EmailVerification` model (user OneToOne, `verified_at`, `last_sent_at`, `created_at`) + schema migration; admin read-only inline on the user
- [x] 1.2 `SIGN_IN_GRACE_HOURS` setting (env, default 24)
- [x] 1.3 `survey/email_verification.py`: `is_verified`, `grace_deadline`, `can_sign_in`, `mark_verified`, `mask_email`, `send_link(user, request, source)` (per-email limit shared with the resend form; records `last_sent_at`; returns sent/limited)
- [x] 1.4 Data migration + idempotent `sync_email_verification` command sharing one rule function (active → confirmed; inactive & never logged in & no content_screen AbuseEvent → active, unconfirmed; inactive with login → untouched, confirmed)
- [x] 1.5 Tests (`survey/tests/test_sign_in_grace_period.py`): the rule, no-row = confirmed, ban beats confirmation, migration rule cases, mask

## 2. Registration and confirmation

- [x] 2.1 `AbuseProtectedRegistrationView.create_inactive_user` override: active user + unconfirmed row + link + `login()`; success → `LOGIN_REDIRECT_URL`; honeypot path unchanged; email-matched invitations accepted on confirmation, not registration
- [x] 2.2 `DirectActivationView`: confirm by `is_verified`, refuse banned, `mark_verified`, keep `user_activated` + sign-in; already-signed-in same user continues
- [x] 2.3 `ResendActivationView` → unconfirmed active accounts via `send_link`
- [x] 2.4 Update `test_account_activation.py`, `test_registration_abuse_defenses.py`, `test_signup_attribution.py` for active-on-register; new scenarios from the account-activation delta

## 3. Sign-in

- [x] 3.1 Extract `find_user(identifier)` in `survey/backends.py`; `user_can_authenticate` → `can_sign_in`; `get_user` keeps `is_active` only
- [x] 3.2 `SignInForm` (`email_unconfirmed` error with masked address + sent flag), wired with `LoginView.as_view(authentication_form=…)` before `django.contrib.auth.urls`
- [x] 3.3 `registration/login.html`: not-confirmed message (sent / already sent), generic message without the resend hint; `?unconfirmed=1` variant
- [x] 3.4 `GracePeriodMiddleware` (session flag, logout + redirect / 401, respondent prefixes skipped) registered after auth middleware
- [x] 3.5 Tests: 1 h ok, 25 h refused with message + one mail, wrong password generic + no mail, banned generic, limit holds, session ended at deadline, confirmed session continues, `/surveys/` untouched

## 4. Holding publish and invitations

- [x] 4.1 `services.errors.EmailUnconfirmed`; checks in `publishing.transition` (to published) and `publish_draft`
- [x] 4.2 Editor mapping (`editor_survey_transition`, `editor_publish_draft`): message with resend button instead of the publish result
- [x] 4.3 REST + MCP mapping: `403 email_unconfirmed` (`api/errors.py`, MCP `isError` envelope); regenerate `reference/api.md` / `reference/mcp-tools.md` if error lists change
- [x] 4.4 `org_send_invitation` check + message
- [x] 4.5 Tests: editor, REST, MCP publish refused; invitation refused; wizard/questions/preview work unconfirmed

## 5. Other `is_active` readers

- [x] 5.1 `api/auth.py`, `api/oauth/validator.py`, `api/oauth/views.py`, `api/v1/responses.py` → `can_sign_in`; fix the `api/auth.py` comment
- [x] 5.2 `survey/funnel.py` activated = `verified_at`; update `test_creator_funnel_dashboard.py`; newsletter recipients and the PostHog activation backfill use `confirmed_q()`
- [x] 5.3 Tests: api/mcp auth unconfirmed within/past grace

## 6. Banner and texts

- [x] 6.1 Context processor + `editor/partials/_confirm_email_banner.html` in `editor_base.html` and `base.html`; resend endpoint (POST, login required, `send_link`)
- [x] 6.2 `registration_complete.html` (honeypot landing), `resend_activation_done.html`, activation mail texts: link validity from `ACCOUNT_ACTIVATION_DAYS`, 24 h grace stated separately
- [x] 6.3 EN + RU catalog entries for every new string (templates and Python), appended by hand; `TranslationCatalogHygieneTest` green
- [x] 6.4 Help centre: update the sign-in / activation page if one exists under `help/src/content/docs/`

## 7. Wrap-up

- [x] 7.1 Run touched test modules, then `./run_tests.sh survey billing api mcp newsletter`
- [x] 7.2 Manual check on the dev server: register → editor, publish held, banner resend, clock past 24 h → sign-in message
- [x] 7.3 Note in the PR: run `sync_email_verification` once after deploy (PR #491; ran on production 2026-10-29 as Render job, 0 rows to fix)

## 8. Remove Cloudflare Turnstile (#490)

- [x] 8.1 Check production: keys empty on the service and the shared group; no widget on the live page
- [x] 8.2 Remove `verify_turnstile`, the view step and context, settings, the widget/script/notice, `render.yaml` keys, `docs/OVERVIEW.md` row, `CLAUDE.md` bullet
- [x] 8.3 `/terms/` (+ `TERMS_UPDATED`) and `/trust/` name the confirmation rule instead
- [x] 8.4 Tests: drop Turnstile-only tests and settings overrides; `TurnstileRemovedTest` guards the page and the policy texts
- [x] 8.5 Spec deltas: `registration-abuse-defenses` (REMOVED + MODIFIED), `render-deployment`
