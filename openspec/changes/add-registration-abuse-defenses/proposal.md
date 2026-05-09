## Why

A subscription-bombing attack on 2026-05-07/08 created 41 bot accounts in 36 hours by automating POSTs to `/accounts/register/`. The attacker's goal was not to use Mapsurvey but to weaponize its welcome-email path against a list of harvested victim addresses (several email addresses appeared on multiple bot accounts). The attack continues at lower volume after manual cleanup — 2 more bot signups appeared within 24 hours.

Without defenses, every additional burst chips at SMTP reputation, which silently degrades deliverability of the live user-outreach campaign (Decisio, StefSier, hmsbrito7 and ~30 other in-flight conversations). This is Phase 1 of the [abuse-prevention epic](../../backlog/epics/abuse-prevention.md) — three layered defenses on the registration endpoint that together block ~99% of automated subscription-bombing scripts.

## What Changes

- **Cloudflare Turnstile** widget on the registration form; server-side verification of the submitted token via Cloudflare's `siteverify` API. Fails closed (no token → request rejected). Dev environments use Cloudflare's published always-pass test keys so local `runserver` is not broken.
- **Per-IP rate limiting** on POST `/accounts/register/` — 3 successful registrations per hour and 10 per day per IP, configurable via env. Backed by a new `CACHES` block pointing at the existing Redis service. Fails open if Redis is unreachable. Real client IP is read via a new `CloudflareIPMiddleware` that copies `CF-Connecting-IP` into `request.cf_ip` (does not overwrite `REMOTE_ADDR`).
- **Honeypot field** named `website` rendered as a hidden input on the registration form. If a non-empty value is submitted, the request is **silently** redirected to the registration-complete page (the bot sees apparent success); no `User` is created and no email is sent.
- **`AbuseEvent` audit log model** — every triggered defense writes one row (defense, ip, user_agent, detail, created_at). Lays the foundation for the Phase 3 anomaly dashboard without retrofitting all call sites later.
- **Hierarchical loggers** `abuse.captcha`, `abuse.ratelimit`, `abuse.honeypot` for ops visibility on Render log tailing.
- New `AbuseProtectedRegistrationView(AsyncEmailRegistrationView)` subclass; existing `AsyncEmailRegistrationView` is left untouched (single-responsibility preserved). URL `accounts/register/` now points at the protected view.

## Capabilities

### New Capabilities
- `registration-abuse-defenses`: behavior of the three layered defenses on the registration endpoint — Turnstile verification, per-IP rate limiting, honeypot field — including their composition order, fail-mode semantics, and observable side effects.
- `abuse-event-log`: the audit log of triggered abuse defenses — schema, lifecycle, and integration contract for any present or future defense module.

### Modified Capabilities
- `render-deployment`: adds 6 abuse-prevention environment variables (`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TRUSTED`, `REGISTRATION_RATE_LIMIT_HOUR`, `REGISTRATION_RATE_LIMIT_DAY`, `REDIS_URL`) to the Render web service config. No removal or redefinition of existing render-deployment requirements.

## Impact

- **New dependencies**: `django-ratelimit`, `django-redis` (added to `Pipfile`). No `requests` — Turnstile siteverify uses stdlib `urllib.request`.
- **New env vars**: `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `REDIS_URL`, `CLOUDFLARE_TRUSTED`, `REGISTRATION_RATE_LIMIT_HOUR`, `REGISTRATION_RATE_LIMIT_DAY`. Production secrets set on Render with `sync: false`; dev defaults in `.env.example` use Cloudflare's public test keys.
- **`render.yaml`**: web service gains `REDIS_URL` from the existing `mapsurvey-redis` service and four new env-var entries.
- **Settings**: adds `CACHES` block (Redis-backed), `LOGGING` config (currently absent), inserts `CloudflareIPMiddleware` near the top of `MIDDLEWARE`.
- **DB migration**: one new migration creating `AbuseEvent`. No changes to `auth_user` or any existing table.
- **Affected code**: `mapsurvey/settings.py`, `mapsurvey/urls.py`, `survey/views.py`, `survey/middleware.py`, `survey/models.py`, `survey/templates/django_registration/registration_form.html`, `survey/abuse.py` (new), `survey/migrations/00XX_abuse_event.py` (new), `Pipfile`, `.env.example`, `render.yaml`.
- **Breaking change**: none. All real users continue to register exactly as before; Turnstile clears legitimate users invisibly in the typical case.
- **Out of scope (separate backlog items, separate changes)**: email verification before account creation, disposable-domain blocklist, unconfirmed-signup auto-purge, anomaly dashboard.
