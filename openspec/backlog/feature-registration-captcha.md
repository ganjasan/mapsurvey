# Registration CAPTCHA (Cloudflare Turnstile)

**Type**: feature
**Priority**: very high
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Add Cloudflare Turnstile (or hCaptcha as fallback) to the registration form at `/register/`. Block bot signups before they can trigger an outbound welcome / verification email. This is the **load-bearing defense** of the abuse-prevention epic — every other measure assumes this is in place.

## Goals

- Block automated registration scripts (the 2026-05-07/08 incident pattern: 41 accounts in 36h with random usernames + harvested emails).
- Zero additional friction for legitimate users — Turnstile's managed mode is invisible in the common case.
- Immediate deployability — no major auth refactor required.

## Why Turnstile, not hCaptcha or reCAPTCHA

- Turnstile defaults to **invisible / managed** challenges. hCaptcha and reCAPTCHA more often surface visible "click the buses" puzzles, which add real friction for users on slow connections / international IPs (most Mapsurvey users are non-US academics).
- Free tier covers our scale comfortably (we register on the order of 10s of users/day in normal traffic).
- No Google dependency — privacy-friendlier for EU academic users (relevant given current pipeline includes RMIT, TU Dortmund, Univ. Milano, York, HEPIA, Bauhaus-Uni Weimar).

## Scope

### In Scope

- Add Turnstile site key + secret env vars (`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`).
- Embed Turnstile widget in registration template.
- Server-side verification of the Turnstile token on POST.
- Reject registration if token missing/invalid.
- Logging on rejection (IP, user-agent, attempted email) for incident response.

### Out of Scope

- CAPTCHA on login (separate concern; brute-force on login is a different attack model).
- CAPTCHA on survey-response submission (would harm legitimate respondent flow).
- CAPTCHA on password reset (handle in a follow-up; same family of risk but different priority).

## Implementation Notes

- Use `django-turnstile` package or roll a 30-line view-mixin — both fine. Roll-your-own keeps dependencies small.
- Verification endpoint: `https://challenges.cloudflare.com/turnstile/v0/siteverify`.
- Mapsurvey is on Render — set the env vars in `render.yaml` and the Render dashboard secrets.
- Local dev: provide a "always-pass" test secret that Cloudflare publishes for development environments.

## Open Questions

- Should we also gate the survey-response endpoint? Probably not — that hurts respondent UX and bots have no incentive there (no email, no account).
- If Turnstile is down / blocked in some regions (e.g. China, Iran — Hossein Vahidi's lab), do we fail-open or fail-closed? Default fail-closed. If we get reports, add a manual-review flow.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling: [feature-registration-rate-limiting.md](feature-registration-rate-limiting.md), [feature-registration-honeypot.md](feature-registration-honeypot.md)
