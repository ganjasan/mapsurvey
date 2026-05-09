## Context

Mapsurvey runs Django on Render, behind Cloudflare. Registration is at `/accounts/register/` and uses `django-registration`'s two-step activation backend. The view is `survey.views.AsyncEmailRegistrationView` (a 30-line subclass that fires the activation email in a background thread). The form is the upstream `django_registration.forms.RegistrationForm` (no project subclass yet). The template lives at `survey/templates/django_registration/registration_form.html`.

The codebase has **no** abuse-prevention machinery today aside from a small cache-based rate-limiter on the analytics beacon (`analytics_views.analytics_track_event`, 120 events/hr per session). There is no `CACHES` block in settings (Django's default `LocMemCache` is in effect), no IP-detection middleware, no `LOGGING` config. Redis exists in `render.yaml` as `mapsurvey-redis` but is wired only into Celery — the web service has no `REDIS_URL` env var.

In production the app sits behind Cloudflare; the real client IP arrives in the `CF-Connecting-IP` header. `REMOTE_ADDR` reflects only the last hop from Render's edge.

The 2026-05-07/08 incident produced 41 bot accounts; manual cleanup required deleting from `survey_membership` first (FK constraint), then from `auth_user`. The attack is ongoing at lower volume (2 more bots seen on 2026-05-08 after cleanup).

## Goals / Non-Goals

**Goals:**
- Block automated subscription-bombing on `/accounts/register/` such that the welcome/activation email is not sent to harvested addresses.
- Zero added friction for legitimate users in the typical case (Turnstile managed mode is invisible).
- Defense-in-depth: three independent layers — Turnstile, rate limit, honeypot — so that a bot bypassing one still hits the next.
- Foundation for Phase 2 (email-confirm-before-account, disposable-domain blocklist, unconfirmed-signup purge) and Phase 3 (anomaly dashboard) without rewrite — single audit-log model already in place.
- Local-dev story: developers running `manage.py runserver` continue to register users without configuring real Turnstile keys or running Redis.

**Non-Goals:**
- CAPTCHA / rate-limit on login, password reset, or survey-response submission. Different threat models, different UX cost.
- Replacing `django-registration` or rewriting auth flow. Scope is purely additive on the existing view.
- WAF / Cloudflare Bot Management at the edge — separate infra epic.
- Email verification before `auth_user` row creation — Phase 2 of the abuse-prevention epic, separate change.
- Disposable-email-domain blocklist — Phase 2.
- Real-time alerting / anomaly dashboard — Phase 3.
- Operational cleanup automation (delete bot accounts on a schedule) — Phase 2.

## Decisions

### D1: Subclass `AsyncEmailRegistrationView` rather than modify in place

`AsyncEmailRegistrationView` has one job — fire the activation email in a background thread. Adding three orthogonal abuse concerns to it bloats SRP. We introduce `AbuseProtectedRegistrationView(AsyncEmailRegistrationView)` and update `mapsurvey/urls.py` to point at the subclass. The original view is unchanged and still importable for tests/admin paths that bypass abuse defenses.

**Alternatives considered**: (a) modify `AsyncEmailRegistrationView` directly — couples concerns, harder to test in isolation; (b) `AbusePreventionMixin` mixin — works but mixin chains in Python are subtle, and we have only one consumer, so the indirection earns nothing. Plain subclass wins on clarity.

### D2: Honeypot validated in the form, fake-success redirect emitted from the view

The honeypot field `website` is added to a new `RegistrationAbuseForm(RegistrationForm)`. `clean_website` sets `self._honeypot_triggered = True` if the field is non-empty (returning empty string so no `ValidationError` surfaces). The view, in `post()`, checks `getattr(form, '_honeypot_triggered', False)` after `is_valid()`. If triggered, it logs to `abuse.honeypot`, writes one `AbuseEvent` row, and **redirects to `django_registration_complete`** — the same URL real successes redirect to. The bot gets no signal that the trap fired.

**Alternatives considered**: returning a 400 (advertises the trap), returning a fake 200 with the same template (workable but breaks `RegistrationView`'s flow contract), validating in the view directly bypassing the form (form is reusable, view handles HTTP).

### D3: Turnstile siteverify in the form's `clean_cf_turnstile_response` (with dev bypass)

The form has a hidden `cf_turnstile_response` field (populated by Cloudflare's JS widget into `name="cf-turnstile-response"`; we map the dash to underscore). `clean_cf_turnstile_response` calls `survey.abuse.verify_turnstile(token, request_ip)`, raising `ValidationError` on failure. **If `settings.TURNSTILE_SECRET_KEY` is empty (local dev with no key configured) the check returns immediately as success.** This keeps `runserver` workable. Cloudflare's published always-pass test keys (`1x00000000000000000000AA` site key, `1x0000000000000000000000000000000AA` secret) are the recommended dev defaults in `.env.example` — they exercise the full code path while always passing.

**Alternatives considered**: verify in the view (loses access to form-validation flow that re-renders the form with errors), verify in middleware (couples middleware to a specific form), use `django-turnstile` package (one more dep, marginal value over 30-line stdlib `urllib.request` call).

### D4: Rate limiting via `django-ratelimit` decorator on `dispatch`, fail-open on Redis outage

`@method_decorator(ratelimit(key='func:survey.abuse.client_ip', rate='3/h', method='POST', block=True))` on `dispatch`. Two stacked decorators give us 3/hour and 10/day. `block=True` raises `Ratelimited`, which we catch and re-render as a 429 with a friendly message and a `Retry-After` header. `RATELIMIT_FAIL_OPEN = True` ensures Redis outage does not lock out signups (graceful degradation; honeypot + Turnstile remain in effect).

The `key` callable lives at `survey.abuse.client_ip` so the same function is used by Turnstile siteverify (which sends client IP to Cloudflare) and the rate-limit key. Single source of truth.

**Alternatives considered**: rolling a manual cache counter (10 lines, but loses `Retry-After`, sliding windows, and django-ratelimit's atomic increment via `cache.add`); `django-axes` (auth-focused, not request-rate-focused).

### D5: Cloudflare IP via small middleware that sets `request.cf_ip`

A new `CloudflareIPMiddleware` (in `survey/middleware.py` alongside the existing `ActiveOrgMiddleware`) reads `HTTP_CF_CONNECTING_IP` and stores it as `request.cf_ip`. It does **not** overwrite `REMOTE_ADDR` — Django internals trust that attribute and silent rewrites are scary. `client_ip(request)` in `survey/abuse.py` reads `request.cf_ip` first and falls back to `request.META["REMOTE_ADDR"]`.

A `CLOUDFLARE_TRUSTED` setting (default `False`) gates the header read. In dev / on a non-Cloudflare deployment the header would be spoofable and reading it untrustworthy. On Render in production the env sets `CLOUDFLARE_TRUSTED=true`.

**Alternatives considered**: `django-ipware` package (overkill; reads many headers heuristically — we know exactly one), inline `request.META.get("HTTP_CF_CONNECTING_IP")` in `client_ip` only (works but the `CLOUDFLARE_TRUSTED` flag plus middleware keeps the trust decision in one auditable place).

### D6: `AbuseEvent` Django model, written from every triggered defense

One model: `AbuseEvent(defense, ip, user_agent, detail, created_at)`. `defense` is a CharField with choices `('captcha', 'ratelimit', 'honeypot', 'email_domain')` — `email_domain` is a future-Phase-2 stub so we don't need a schema change later. Indexed on `defense` and `created_at` for the eventual Phase 3 dashboard query (`AbuseEvent.objects.filter(defense='honeypot').count()`).

**Alternatives considered**: log-only (cheap but Phase 3 dashboard needs DB; retrofitting all defense call sites later is more work than adding one model now); generic `AuditEvent` model used by other features (no other features need this; YAGNI).

### D7: `django-redis` package for cache backend, not built-in `RedisCache`

`django.core.cache.backends.redis.RedisCache` was added in Django 4.0. The project's settings.py header says "Django 2.2" but `Pipfile` has `django = "*"` (unpinned), and `pip show django` would be the only authoritative answer. To avoid an import-error surprise on production, use `django_redis.cache.RedisCache` from the `django-redis` package — works on every Django version we'd plausibly run.

**Alternatives considered**: built-in `RedisCache` (simpler, no new dep — but only on Django 4+); `python-memcached` (no Redis already provisioned for memcached).

### D8: Hierarchical loggers `abuse.captcha`, `abuse.ratelimit`, `abuse.honeypot`

Three loggers, all routed to console by default. `logging.getLogger("abuse")` aggregates all three. Production can route specific loggers to Sentry or PagerDuty without touching code. The `AbuseEvent` DB row is the authoritative record; loggers are operational noise for Render log tailing.

## Risks / Trade-offs

- **Cloudflare outage blocks all registrations** (Turnstile fail-closed) → Mitigation: Cloudflare's uptime is meaningfully higher than the app's. We accept this. If it becomes a problem, switch to fail-open with a 5-second timeout (already in code).
- **Redis outage → rate-limit silently disabled** (fail-open) → Mitigation: `RATELIMIT_FAIL_OPEN=True` is intentional; honeypot + Turnstile remain active and catch most bots even without rate limit. Redis outage on Render is rare and short-lived.
- **`CF-Connecting-IP` spoofing if `CLOUDFLARE_TRUSTED=true` is set on a non-Cloudflare deployment** → Mitigation: setting defaults to `False`; production-only override; documented in `.env.example`.
- **Legitimate classroom signups (Mora school, NYU labs) hit per-IP/day=10 limit** → Mitigation: configurable via `REGISTRATION_RATE_LIMIT_DAY` env. Real classroom contexts are rare enough that bulk-creation via admin is acceptable.
- **`django-redis` adds a dep that could conflict with future Django upgrades** → Mitigation: `django-redis` tracks Django releases closely; if it becomes unmaintained we switch to the built-in backend.
- **Honeypot field `website` collides with a future legitimate "website" field** → Mitigation: low likelihood (registration form is identity-only, never a profile field); if needed, rename via env `ABUSE_HONEYPOT_FIELD`.
- **Turnstile widget fails to load on slow / restrictive networks (China, Iran, corporate firewalls)** → Mitigation: Cloudflare publishes regional fallbacks; if user reports surface, document the behavior or add an opt-out manual-review queue. Out of scope for this change.
- **Tests using the test client must pass valid Turnstile tokens** → Mitigation: in tests, leave `TURNSTILE_SECRET_KEY` unset; the form skips siteverify when secret is empty. Documented in the test setup.

## Migration Plan

This is purely additive — no destructive DB ops, no changes to existing behavior for legitimate users.

**Deploy order:**
1. Apply DB migration (`AbuseEvent` table). Trivial — no data backfill.
2. Deploy app code with `ABUSE_PREVENTION_ENABLED=True` (default).
3. Set `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TRUSTED=true`, `REDIS_URL` env vars on Render web service.
4. Verify on staging (or test endpoint) that:
   - Real signup with valid Turnstile passes
   - POST without `cf-turnstile-response` is rejected
   - Honeypot-filled POST returns 302 to complete page, no user created
   - 4th rapid POST from same IP returns 429

**Rollback:** revert URL conf to point back at `AsyncEmailRegistrationView`. Migration can stay (the table is empty if rolled back immediately). Three env vars can be unset; defaults are safe (Turnstile falls back to dev-bypass when secret is empty).

**Local dev:** `.env.example` ships with Cloudflare's always-pass test keys. Developers don't need to configure anything new. Redis is only required if you want to exercise rate-limiting locally (otherwise the `LocMemCache` fallback works for single-process dev).

## Open Questions

- **Tests for rate-limit require Redis** — do we run them by default in CI, or skip with `@skipUnless(REDIS_URL)`? Recommendation: skip in unit-test runs; cover with a separate integration-test target.
- **Privacy notice copy** — the change adds a one-line "Protected by Cloudflare Turnstile" note under the widget linking to Cloudflare's privacy policy. Final copy goes in implementation; document if a translation pass is needed before ship.
- **`CLOUDFLARE_TRUSTED` default in `.env.example`** — `false` (dev) or `true` (matches prod)? Recommendation: ship `false` so devs don't accidentally trust spoofed headers locally. Render's env overrides to `true`.
