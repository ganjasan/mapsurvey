# Reduce duplicate accounts / signup-login UX friction

**Type**: improvement
**Priority**: medium
**Area**: backend
**Epic**: —
**Created**: 2026-06-10
**Related**: [Email Verification Before Account Creation](feature-email-verification-before-account.md), [Growth epic](epics/growth.md)

## Description

A meaningful share of users hold 2–3 accounts on the *same email address*, signalling friction in the signup/login flow (people re-register instead of logging back in, or create variants when something fails). Reduce duplicate-account creation and make returning users land back in their existing account.

## Evidence (2026-06-10 analysis)

When grouping real registrations by email domain, most institutional "clusters" with ≥2 accounts turned out to be **the same person duplicated**, not teams:

- rivco.org (ricastel + ricastell), ufu.br (jessicalvesfs ×2), rmit.edu.au (jessica.rivera ×2), columbia.edu (mountvernon + mountvernonstudio), lichtblick.de (Fränze + fraenze), line-grade.com (hannah + hannahetter).
- Plus many same-email pairs among gmail users (e.g. Echa/vnecha, abeee/abeeeeee, edginakyut/edginakyuttt, anin18/anin8, several FTSPK variants).

These are not abuse — they're real users who registered twice. That points to a login/recovery UX gap.

## Scope / ideas

- **Detect existing email at signup**: if the email already exists, route to login + password-reset instead of silently creating a second account (note: must stay compatible with the honeypot/abuse flow which returns fake-success — don't leak account existence to bots; apply this only post-Turnstile or via the password-reset path).
- **Prominent "forgot password / log in instead"** affordance on the registration page.
- **Case-insensitive / normalized email uniqueness** so `INFO@…` vs `info@…` don't diverge.
- Optional: a one-off admin merge tool for known duplicates (the user-outreach docs already track the duplicate map).

## Notes

- Distinct from abuse-prevention (those are bots/spam); this is genuine-user friction, but the two interact at the signup endpoint — coordinate with `AbuseProtectedRegistrationView` and the email-verification feature.
- Activation angle: a returning user who lands in their existing account (with their draft survey) is far likelier to reactivate than one who starts a fresh empty account.
- Low-risk, medium-value; sequence after abuse-prevention Phase 1 since both touch the registration view.
