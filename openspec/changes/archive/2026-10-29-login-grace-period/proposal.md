## Why

A new creator who returns to the sign-in page before opening the activation mail gets
"Invalid username/email or password" for a correct password, because an unactivated account
cannot authenticate at all. Replay Vision caught one on 2026-10-27 (issue #487): seven sign-in
attempts in 66 seconds, then activation, then the person left without creating a survey. The
mail is a wall in front of the product at exactly the moment interest is highest, and the
message on that wall is false.

## What Changes

- **A new account signs in immediately**, with no activation, for a **24-hour grace period**
  counted from registration. Registration lands the creator in the editor signed in, and the
  "check your email" message becomes a banner there instead of a dead-end page.
- **After 24 hours without confirming the address**, sign-in with the correct password is
  refused with the real reason ("you did not confirm your email within 24 hours — we have sent
  a new link to a•••@example.org"), and a fresh activation mail goes out (rate-limited). There is
  no second grace period: the link, which signs the creator in on confirmation, is the way in.
  A session opened during the grace period ends at its next request after the 24 hours.
- A wrong password keeps the generic message, so the new message reveals nothing to someone
  who does not already hold the password.
- **During the grace period**, everything works except **publishing a survey** (the editor, the
  REST API and MCP alike) and **inviting someone to a workspace**: both wait for a confirmed
  address, and say so with a resend action.
- **BREAKING (internal)**: `User.is_active` stops meaning "activated". New accounts are created
  active; confirmation lives in a new `EmailVerification` record. `is_active=False` keeps one
  meaning, a ban (`content_screening.confirm_phishing`), so a banned account never receives a
  "confirm your email" message or link. Every reader of `is_active`-as-activation (resend,
  API/OAuth authentication, the staff funnel) moves to the new record.
- Data migration: active accounts become confirmed; never-activated accounts become active,
  unconfirmed, grace expired (their next sign-in gets the new message and a link); banned
  accounts are untouched.
- **Cloudflare Turnstile is removed** (#490, owner decision 2026-10-29). Both keys were empty in
  production, so every sign-up already took the empty-secret bypass, while `/terms/` and `/trust/`
  still promised it. Registration keeps the honeypot and the per-IP limits; the policy pages now
  name the confirmation rule instead.
- The "check your email" texts state the truth: the 24-hour sign-in grace, and the link's own
  validity (`ACCOUNT_ACTIVATION_DAYS`, 7 days) — today one page says 24 hours and another a
  hard-coded 7 days.

## Capabilities

### New Capabilities
- `sign-in-grace-period`: sign-in without confirmation for 24 hours, the explicit refusal and
  automatic resend after it, the end of grace-period sessions, and the actions held until the
  address is confirmed (publish, invite).

### Modified Capabilities
- `account-activation`: activation now confirms an address on an active account rather than
  activating an inactive one; resend targets unconfirmed accounts; the "already active" repeat
  becomes "already confirmed"; the validity-window texts follow the setting.
- `auth-form-feedback`: the sign-in failure message is no longer always generic — a correct
  password on an unconfirmed account past its grace period gets the specific message.
- `registration-abuse-defenses`: the Turnstile requirement is removed; composition order, the
  rate-limit counters, the legitimate-registration flow (active, signed in) and configuration
  lose their Turnstile clauses.
- `render-deployment`: `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` leave the environment table.
- `api-authentication`: a bearer token is refused for an account that cannot sign in (banned,
  or unconfirmed past the grace period), not for "`is_active` false (or never activated)".
- `creator-funnel-dashboard`: the "activated" stage counts confirmed addresses, not `is_active`.

## Impact

- Code: `survey/backends.py` (authentication gate), a custom `AuthenticationForm` for the
  specific message and resend, `survey/views.py` (registration signs in; `DirectActivationView`,
  `ResendActivationView`), a new `survey/email_verification.py` helper module and
  `EmailVerification` model + migrations (schema, then data), a middleware check for expired
  grace sessions, `survey/services/publishing.py` (`transition`, `publish_draft`),
  `survey/org_views.py::org_send_invitation`, `api/auth.py`, `api/oauth/validator.py`,
  `api/oauth/views.py`, `survey/funnel.py`, templates (`registration/login.html`,
  `django_registration/*`, an editor banner partial), EN + RU catalogs.
- Events: `creator_activated_account` keeps firing on confirmation; nothing new is emitted for
  the grace sign-in beyond the usual login.
- Abuse: honeypot and registration rate limits are unchanged, Turnstile (already off) is removed;
  publishing still needs a live mailbox. Automatic resend at sign-in shares the per-email limit.
- Supersedes point 1 of `openspec/backlog/improvement-inactive-account-dead-ends.md`.
