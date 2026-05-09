## ADDED Requirements

### Requirement: Abuse-prevention environment variables

The Render web service SHALL provide the following environment variables consumed by the registration abuse defenses (see [registration-abuse-defenses](../registration-abuse-defenses/spec.md)).

| Variable | Source | Notes |
|---|---|---|
| `TURNSTILE_SITE_KEY` | `sync: false` (set per-environment in Render dashboard) | Public Cloudflare Turnstile site key — rendered into the registration template |
| `TURNSTILE_SECRET_KEY` | `sync: false` | Cloudflare Turnstile secret — used by `verify_turnstile()` server-side. Empty value disables verification (dev mode only) |
| `CLOUDFLARE_TRUSTED` | `value: "True"` (production behind Cloudflare) | Gates `CloudflareIPMiddleware` reading `HTTP_CF_CONNECTING_IP`. MUST be False on any deployment not behind Cloudflare or the header is spoofable |
| `REGISTRATION_RATE_LIMIT_HOUR` | `value: "3"` | Per-IP hourly limit on POST `/accounts/register/` |
| `REGISTRATION_RATE_LIMIT_DAY` | `value: "10"` | Per-IP daily limit |
| `REDIS_URL` | `fromService: type=redis name=mapsurvey-redis property=connectionString` | Reuses the existing Redis service. Used by `CACHES["default"]` for rate-limit counters |

#### Scenario: Turnstile keys provided as secrets

- **WHEN** the Render web service starts
- **THEN** `os.environ["TURNSTILE_SITE_KEY"]` and `os.environ["TURNSTILE_SECRET_KEY"]` SHALL be set to the values configured in the Render dashboard (not committed to render.yaml)

#### Scenario: REDIS_URL wired from existing service

- **WHEN** Render reads render.yaml
- **THEN** the `REDIS_URL` env var on the `mapsurvey` web service SHALL be sourced from the `mapsurvey-redis` service's `connectionString` property
- **AND** the same Redis instance SHALL be reachable from both web and Celery workers

#### Scenario: CLOUDFLARE_TRUSTED forced to True in production

- **WHEN** the production deployment is provisioned from render.yaml
- **THEN** `CLOUDFLARE_TRUSTED` SHALL be set to `"True"` so that `CF-Connecting-IP` is honored as the real client IP

#### Scenario: Rate-limit thresholds configurable without redeploy

- **WHEN** an operator updates `REGISTRATION_RATE_LIMIT_HOUR` or `REGISTRATION_RATE_LIMIT_DAY` in the Render dashboard
- **THEN** the values SHALL take effect on the next service restart
- **AND** no code change SHALL be required
