# Streamline Registration

## Why

Registration is the funnel's tightest bottleneck and the weekend of 2026-08-22/23 produced 9 live
visitors and 0 registrations. Per-visit forensics (PostHog sessions + Render request logs +
`AbuseEvent`) showed three independent friction sources: both users who actually submitted the form
were bounced by form validation (4 visible fields, exact error unknown — we don't log it), one user
was locked out by a client-side Cloudflare Turnstile failure (error 300010), and the rest never
started typing. Lifetime `AbuseEvent` data shows Turnstile has caught ~1 bot ever (vs 1442 for the
honeypot) while measurably losing at least 5–6 real humans (`missing_token` / `siteverify_rejected`
from real browser UAs, plus silent widget failures that never reach a POST). Every registration is
worth more than the spam it might admit: leads are worked for design-partner access, not revenue.

## What Changes

- **Minimal registration form**: reduce to email + single password. Username is auto-derived from
  the email local part (deduplicated); the password-confirmation field is dropped (password reset
  covers typos). Honeypot and per-IP rate limit stay. The live password checklist stays.
- **Social sign-in via django-allauth**: Google only in this release. Provider buttons on both the
  registration and login pages. OAuth accounts skip email activation (the provider has already
  verified the address) and skip the password fields entirely. The allauth wiring is
  provider-agnostic so follow-up changes add providers by configuration: Microsoft is next
  (separate change), ORCID/GitHub/Facebook stay in the backlog.
- **Turnstile removed** (same release): widget, siteverify call, and the `captcha` defense retire.
  Env vars `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` are cleared on Render at release time; code
  is deleted rather than kept dormant. **BREAKING** for the `registration-abuse-defenses` spec:
  the three-layer model becomes two-layer (honeypot + rate limit).
- **Registration failure observability**: server-side event when a registration POST fails
  validation, carrying the names of the failing fields and error codes (never values — the fields
  are email and password) so the next silent weekend is diagnosable. (Rate-limit accounting was
  already fixed in `registration-rate-limit-traps-humans` / PR #97 — validation failures no longer
  consume the per-IP budget; this change does not touch it.)

## Capabilities

### New Capabilities

- `social-sign-in`: OAuth registration/login (Google in this release; the capability is written
  provider-agnostic) — account creation, linking to existing email-matched accounts, activation
  bypass, and the provider-button UI on auth pages.

### Modified Capabilities

- `registration-abuse-defenses`: Turnstile layer removed; defense contract becomes
  honeypot + rate limit; `captcha` defense retired from `AbuseEvent` writers (historic rows keep
  the value).
- `account-activation`: email-activation requirement scoped to password registrations only;
  OAuth-verified emails activate immediately.
- `signup-attribution`: registration form field set changes (username removed, single password);
  attribution capture must survive both the short form and the OAuth callback path.

## Impact

- **Code**: `survey/abuse.py` (Turnstile verify + form), `survey/views.py`
  (`AbuseProtectedRegistrationView`), `survey/templates/django_registration/registration_form.html`,
  login template, `mapsurvey/settings.py` + `mapsurvey/urls.py` (allauth apps, middleware, urls),
  new migration(s) for allauth tables.
- **Dependencies**: `django-allauth` added to Pipfile.
- **Ops**: one OAuth client registration (Google Cloud Console) with credentials as Render env
  vars. Redirect URIs must cover production and PR-preview hosts.
- **Data/privacy**: `/trust/` page and DPA must list Google Sign-In as a processor; Cloudflare
  Turnstile is removed from the same documents.
- **Funnel**: `creator-funnel-dashboard` registration counts must treat OAuth signups identically
  to form signups (`creator_registered` fires on both paths).
