## Context

Registration goes through django-registration's activation backend: `create_inactive_user` saves
the account with `is_active=False` and mails a signed key; `DirectActivationView` (GET shows a
button, POST activates and signs in — scanners pre-fetch links) flips `is_active`. Sign-in is the
stock `LoginView` + `AuthenticationForm` over `survey.backends.EmailOrUsernameBackend`, whose
inherited `user_can_authenticate` rejects inactive accounts — so an unactivated account with the
right password looks exactly like a wrong password. `is_active=False` is also the phishing ban
(`content_screening.confirm_phishing`), and `is_active` is read as "activated" by the resend view,
`api/auth.py`, the OAuth authorize page and refresh grant, and the staff funnel.

Owner decisions (2026-10-29, #487): sign in without confirmation for 24 hours; after that, a
correct password gets the real reason and a fresh link, and only the link lets the account in;
during the 24 hours nothing goes live (publish, invitations).

## Goals / Non-Goals

**Goals:**
- One place that answers "is this address confirmed / may this account sign in".
- The real reason on the sign-in page, only to someone who has proven the password.
- Banned accounts indistinguishable from today: generic message, no mail.
- Nothing published from an unconfirmed mailbox, on any surface.

**Non-Goals:**
- Re-registration with an address that has an unconfirmed account (point 2 of the backlog item
  `improvement-inactive-account-dead-ends`) — separate change.
- Changing the activation key format, the 7-day key validity, or the POST-confirm flow.
- Email change / re-verification for an existing account.

## Decisions

### 1. A separate `EmailVerification` record; `is_active` means "not banned"
`EmailVerification(user OneToOne, verified_at null, last_sent_at null, created_at)`. Registration
creates the user active plus an unconfirmed row.
- *Alternative: keep `is_active=False` until confirmation and let the backend admit inactive
  users during the grace.* Rejected: Django's session machinery (`ModelBackend.get_user`) and
  every `is_active` reader (API, OAuth, admin) would treat a grace-period creator as banned, and
  a ban would become indistinguishable from "not confirmed" — the banned account would get a
  "confirm your email" mail.
- *Alternative: a field on `CreatorPreferences`.* Rejected: that model holds choices the creator
  makes; confirmation is a fact about the account, and a row-per-user table with one obvious
  name is easier to audit and backfill.
- **No row = confirmed.** Superusers from `createsuperuser`, admin-created staff and test
  fixtures keep working with no extra setup. Registration is the only path that creates creators,
  and it always writes a row.

### 2. `survey/email_verification.py` is the one rule
`is_verified(user)`, `grace_deadline(user)` (`date_joined + SIGN_IN_GRACE_HOURS`, env, default
24), `can_sign_in(user)`, `mark_verified(user)`, `send_link(user, request, *, source)` (the one
sender: registration, resend form, banner button, refused sign-in, expired session — all under
the existing per-email resend limit `RESEND_ACTIVATION_RATE_LIMIT_DAY`, keyed on the address; it
returns whether a mail went out), and `mask_email()`. Readers never compute the deadline
themselves.

### 3. Sign-in: backend gate + form that knows the one exception
`EmailOrUsernameBackend.user_can_authenticate` → `can_sign_in`. A custom `SignInForm`
(`AuthenticationForm` subclass, wired via `LoginView.as_view(authentication_form=…)` ahead of
`django.contrib.auth.urls`) overrides `clean()`: when `authenticate()` returns `None`, it looks
the identifier up with the backend's own lookup (`find_user`, extracted so the two cannot
diverge), and only if `check_password` passes, `is_active` is true and the account is unconfirmed
past its deadline does it call `send_link` and raise `ValidationError(code='email_unconfirmed')`
carrying the masked address and whether a mail was sent. Every other failure keeps
`invalid_login`. The template branches on the code.
- *Alternative: let the backend return the user and refuse in `confirm_login_allowed`.* Rejected:
  `authenticate()` is also what the API, admin and `login()` callers use; a backend that returns
  an account that may not sign in invites a future caller to skip the check.
- Cost: one extra `check_password` (PBKDF2) on the failed-login path only. A wrong password
  already costs one, and a mail goes out only through `send_link`'s per-email limit.

### 4. Sessions opened during the grace end at the deadline: `GracePeriodMiddleware`
After `AuthenticationMiddleware`: for an authenticated user whose session lacks the
`ms_email_ok` flag, check `can_sign_in`; if confirmed, set the flag (one query per session, not
per request); if past the deadline, `logout()` and redirect HTML requests to
`/accounts/login/?unconfirmed=1` (the login page then shows the message; the link is sent through
`send_link` with the same limit), JSON/HTMX requests get `401`. Paths under `/surveys/` and `/r/`
are skipped — respondent pages never depend on the creator session. `ModelBackend.get_user`
keeps checking only `is_active` (via a `get_user` override) so the middleware, not a silent
anonymous user, ends the session and can say why.

### 5. Registration signs in
`AbuseProtectedRegistrationView.create_inactive_user` is overridden (name kept for the upstream
hook) to save the user active, create the `EmailVerification` row, send the link, then
`login(request, user, backend=…)`; success redirects to the start page `?welcome=1`. Honeypot,
rate limits run before it unchanged (Turnstile is removed, decision 10); the honeypot's fake success still lands on
the "check your email" page and creates nothing.

### 6. Confirmation
`DirectActivationView` overrides `get_user`/`activate` to check `is_verified` instead of
`is_active` (already confirmed → the existing "already_activated" path, no sign-in), refuse
banned accounts, `mark_verified`, emit `user_activated` as today, and sign in. If the visitor is
already signed in as the same account the session simply continues.

### 7. Nothing goes live from an unconfirmed address
`services/publishing.transition(..., status='published')` and `publish_draft` raise a new
`services.errors.EmailUnconfirmed` when `actor.user` is unconfirmed. The editor maps it to a
modal message with the resend button (replacing the publish confirmation), REST and MCP to
`403 email_unconfirmed` through the existing error mapping (`api/errors.py` gains the code).
`org_send_invitation` checks the same before creating the `Invitation`. The publish button stays
visible: hiding it would hide the reason.

### 8. Every `is_active`-as-activation reader moves
`api/auth.py`, `api/oauth/validator.py` (refresh grant), `api/oauth/views.py` (authorize page),
`api/v1/responses.py` → `can_sign_in`. `ResendActivationView` selects unconfirmed, active
accounts. `survey/funnel.py` "activated" = `verified_at` set (the dashboard's logged-in stage can
now exceed it, which is the new behaviour being measured).

Found while implementing: two more readers equated `is_active` with a confirmed mailbox.
The registration signal auto-accepted invitations sent to the new account's address — with a
grace period that becomes "type an invited address, sign in, join the workspace" — so it moved to
a `user_activated` receiver (`accept_invitations_for_email`); invitation links are unaffected.
`newsletter.Campaign.get_recipient_queryset` and the PostHog activation backfill now filter on
`email_verification.confirmed_q()`.

### 9. Banner
`survey.context_processors.email_verification` returns the address, deadline and resend URL for
an unconfirmed signed-in creator; `editor/partials/_confirm_email_banner.html` is included from
`editor_base.html` and `base.html` (the dashboard extends `base.html`), never from respondent
bases. The resend button POSTs to a small login-required endpoint that calls `send_link`.

### 10. Cloudflare Turnstile is removed (#490)
Checked 2026-10-29: `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are empty on the web service
and in `mapsurvey-shared`, the live registration page loads no Cloudflare script, so
`verify_turnstile()` passed every sign-up through its empty-secret bypass. The owner had switched
it off on purpose and decided to remove it with this change. Gone: `verify_turnstile`, the view
step, settings, the widget/script/notice, `render.yaml` keys, the tests that exercised only it.
Kept: `AbuseEvent`'s `captcha` choice (old rows stay readable; no migration). `/terms/` (+
`TERMS_UPDATED`) and `/trust/` stop claiming it and name the confirmation rule instead.
- *Alternative: keep the code dormant behind empty keys.* Rejected by the owner; dormant code also
  kept two policy pages untrue.

## Risks / Trade-offs

- [Phishers get 24 hours inside the editor without a mailbox] → publish and invitations are
  held; rate limits unchanged. **Accepted (owner, 2026-10-29):** the Testing status and its
  tokenised test link are not held, and content screening does not run on Testing, so an
  unconfirmed account can hand a working survey URL to anyone for up to 24 hours. Testing on a
  phone and with colleagues is part of building; holding it would be one more
  `_require_confirmed_email` call if abuse shows up there.
- [Deploy window: the old instance serves registrations for ~70 s after the migration and creates
  `is_active=False` users with no row, which the new code reads as banned] → the data migration's
  rule is also a management command `sync_email_verification` (idempotent, same rule); run it
  once after the deploy. Accounts with `is_active=False`, no `last_login` and no row are exactly
  that case.
- [A banned account that never signed in would be migrated as "never activated"] → impossible in
  practice: a ban follows a publish, which needs a signed-in session; the migration also skips
  any user with an `AbuseEvent(defense='content_screen')`.
- [Masked address reveals the domain] → shown only after the correct password.
- [Rollback] → reverting the code leaves new accounts active and unconfirmed, i.e. fully usable
  under the old rules; nothing breaks, the table is ignored.

## Migration Plan

1. Schema migration: `EmailVerification`.
2. Data migration (same release, reversible as a no-op): rows for every user by the rule in the
   `sign-in-grace-period` spec; never-activated users flipped to `is_active=True`.
3. Deploy; then `python manage.py sync_email_verification` once (deploy-window registrations).
4. Check on prod: count of unconfirmed rows ≈ count of `is_active=False, last_login IS NULL`
   before the deploy.

## Open Questions

- None blocking. The 24-hour constant is a setting (`SIGN_IN_GRACE_HOURS`) if the owner wants to
  tune it after watching the funnel.
