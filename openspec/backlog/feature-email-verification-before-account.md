# Email Verification Before Account Creation

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Move the `auth_user` insert from "registration form submitted" to "verification link clicked". Today, a successful POST to `/register/` creates the row immediately and sends a confirmation email. The bot in the 2026-05-07/08 incident polluted the DB with 41 unconfirmed accounts — they had no incentive to click the email but the row was there anyway.

After this change: the registration form stores a pending-signup record (or a signed token) and sends the verification email. The user row is created **only** when the recipient clicks the link. If they never click, nothing persists.

## Goals

- Stop bot floods from polluting `auth_user` even when CAPTCHA / rate-limits fail or are bypassed.
- Make the signup-conversion funnel measurable (`registration_attempts` vs `accounts_created` becomes meaningful).
- Reduce admin cleanup burden when the next incident slips past Phase 1 defenses.

## Why this is Phase 2, not Phase 1

CAPTCHA + rate-limits + honeypot stop the **outbound spam attack** (the actual harm). This change stops the **DB pollution side-effect**. They are independent — both should ship, but the email-cannon problem is the user-facing emergency.

This change is also more invasive: it touches the auth flow, requires a pending-signups table or a signed-token implementation, and needs careful test coverage on edge cases (link expiry, double-clicking, account already exists with that email).

## Scope

### In Scope

- Pending-signup mechanism: either a new `signup_token` table or a Django signed-token (`itsdangerous` style) — pick the simpler one that works.
- New endpoint: `/register/confirm/<token>/` that creates the actual `auth_user` row.
- Token expiry (24h is standard).
- Throttling: ignore re-submissions of the same email within the token TTL (resend a link instead of issuing a new one — prevents the form itself from being weaponized for email floods).
- UX: clear messaging on the registration page ("we sent you a link, click it to finish").
- UX: handling for "I never got the email" — single resend button, rate-limited.

### Out of Scope

- Login flow changes (separate concern).
- Password reset flow rewrite — already token-based.
- Migrating existing unconfirmed users (we just deleted the only existing problem cohort manually).

## Open Questions

- Use Django allauth (replaces a lot of auth code) vs. roll-our-own minimal flow? Allauth is heavy; roll-your-own is ~50 lines. Default to roll-your-own unless we already plan to adopt allauth for OAuth.
- Token storage: signed cookie (stateless, simpler, but verification-link emails would carry the cookie via URL — fine, we already do that for password reset) vs. DB table (auditable, slightly more work). Default to signed token for MVP.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling Phase 1: [feature-registration-captcha.md](feature-registration-captcha.md), [feature-registration-rate-limiting.md](feature-registration-rate-limiting.md), [feature-registration-honeypot.md](feature-registration-honeypot.md)
- Sibling: [feature-unconfirmed-signup-purge.md](feature-unconfirmed-signup-purge.md) — auto-purge stale unconfirmed signups
