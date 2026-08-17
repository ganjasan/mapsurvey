# render-deployment Specification

## Purpose

Defines how Mapsurvey is deployed to Render — service topology (web, worker, database, redis), runtime configuration, environment variables, and the contract between `render.yaml` and the running services.
## Requirements
### Requirement: render.yaml Blueprint configuration
Проект SHALL содержать файл `render.yaml` в корне репозитория с декларативной конфигурацией всех сервисов Render.

#### Scenario: Blueprint defines web service
- **WHEN** Render читает render.yaml
- **THEN** создаётся Web Service с Docker runtime, корректным Dockerfile path и start command

#### Scenario: Blueprint defines database
- **WHEN** Render читает render.yaml
- **THEN** создаётся PostgreSQL database на плане Starter с поддержкой PostGIS

### Requirement: Web service configuration
Web Service SHALL быть настроен для запуска Django приложения через Gunicorn.

#### Scenario: Docker build succeeds
- **WHEN** Render собирает Docker image
- **THEN** сборка завершается успешно с установленными геозависимостями (GDAL, PROJ)

#### Scenario: Application starts correctly
- **WHEN** контейнер запускается
- **THEN** Gunicorn слушает порт из переменной окружения PORT

#### Scenario: Health check passes
- **WHEN** Render выполняет health check
- **THEN** приложение отвечает HTTP 200

### Requirement: Database connection
Приложение SHALL подключаться к Render PostgreSQL с PostGIS расширением.

#### Scenario: Database URL parsing
- **WHEN** задана переменная DATABASE_URL
- **THEN** Django парсит её и подключается к PostgreSQL

#### Scenario: PostGIS extension available
- **WHEN** приложение выполняет геозапросы
- **THEN** PostGIS функции доступны в базе данных

### Requirement: Environment variables
Все секреты и конфигурация SHALL передаваться через environment variables.

#### Scenario: Required variables defined
- **WHEN** приложение запускается на Render
- **THEN** доступны переменные: SECRET_KEY, DATABASE_URL, DJANGO_ALLOWED_HOSTS

#### Scenario: Debug mode disabled
- **WHEN** приложение работает в production
- **THEN** DEBUG=0

### Requirement: Static files serving
Статические файлы SHALL раздаваться через Whitenoise.

#### Scenario: Static files collected
- **WHEN** выполняется collectstatic
- **THEN** файлы собираются в STATIC_ROOT

#### Scenario: Whitenoise serves static
- **WHEN** браузер запрашивает /static/*
- **THEN** Whitenoise отдаёт файлы с правильными заголовками кэширования

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

### Requirement: AI provider environment variables
The AI generation credentials SHALL be provided via environment variables with
`sync: false` (never committed; the repo is public): the selected provider's key
(`ANTHROPIC_API_KEY` or `GEMINI_API_KEY`) on both the web service (gates the UI panel)
and the Celery worker service (makes the provider calls), plus optional
`AI_SURVEY_DRAFT_MODEL`, `GEMINI_MODEL`, and `AI_REQUEST_TIMEOUT_SECONDS` overrides.
`AI_PROVIDER` SHALL be declared in the Blueprint rather than left to the settings default,
and SHALL hold the same value on web and worker: the gate is per-provider, so a mismatch
either hides the panel while a key is present or shows a panel whose generations all fail.
An unset key for the selected provider SHALL disable the feature without errors on every
service.

#### Scenario: Provider and key present on web and worker
- **WHEN** the production Blueprint is provisioned
- **THEN** `AI_PROVIDER` carries the same value on `mapsurvey-web` and `mapsurvey-celery`, that provider's key is declared with `sync: false` on both, and the key's value is set only via the Render dashboard

#### Scenario: Key absent
- **WHEN** a service starts without a key for the selected `AI_PROVIDER`
- **THEN** the application boots normally and the AI generation feature is simply off

### Requirement: Celery worker on PR previews
The Celery worker service SHALL be enabled on PR preview environments so that
worker-dependent features (AI draft generation) are verifiable before merge. The cron
service SHALL remain excluded from previews.

#### Scenario: Preview gets a worker
- **WHEN** a PR preview environment is generated from render.yaml
- **THEN** a `mapsurvey-celery` preview instance is created alongside the web preview and processes enqueued tasks

#### Scenario: Cron stays off previews
- **WHEN** a PR preview environment is generated
- **THEN** no acquisition-sync cron service is created for the preview
