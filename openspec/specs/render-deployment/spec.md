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
Web Service SHALL быть настроен для запуска Django приложения через Gunicorn с явной
конфигурацией конкурентности: worker class `gthread`, число воркеров и тредов задаются
переменными окружения (`WEB_CONCURRENCY`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT`) с
дефолтами, дающими не менее 8 одновременных слотов запросов (2 воркера × 4 треда).

#### Scenario: Docker build succeeds
- **WHEN** Render собирает Docker image
- **THEN** сборка завершается успешно с установленными геозависимостями (GDAL, PROJ)

#### Scenario: Application starts correctly
- **WHEN** контейнер запускается
- **THEN** Gunicorn слушает порт из переменной окружения PORT

#### Scenario: Health check passes
- **WHEN** Render выполняет health check
- **THEN** приложение отвечает HTTP 200

#### Scenario: Multiple concurrent requests are served
- **WHEN** контейнер запускается без переопределения переменных окружения
- **THEN** Gunicorn работает с worker class `gthread`, 2 воркерами и 4 тредами на воркер
- **AND** не менее 8 запросов обрабатываются одновременно без выстраивания в очередь

#### Scenario: Concurrency tunable without rebuild
- **WHEN** оператор задаёт `WEB_CONCURRENCY`, `GUNICORN_THREADS` или `GUNICORN_TIMEOUT`
  в Render dashboard и перезапускает сервис
- **THEN** Gunicorn применяет новые значения без пересборки образа

### Requirement: Database connection
Приложение SHALL подключаться к Render PostgreSQL с PostGIS расширением, используя
персистентные соединения (`CONN_MAX_AGE` > 0 c `CONN_HEALTH_CHECKS`): соединение
переживает HTTP-запрос и переиспользуется тредом gunicorn. Время жизни настраивается
переменной окружения `DB_CONN_MAX_AGE` (дефолт 300 секунд).

#### Scenario: Database URL parsing
- **WHEN** задана переменная DATABASE_URL
- **THEN** Django парсит её и подключается к PostgreSQL

#### Scenario: PostGIS extension available
- **WHEN** приложение выполняет геозапросы
- **THEN** PostGIS функции доступны в базе данных

#### Scenario: Connections survive across requests
- **WHEN** два HTTP-запроса подряд обрабатываются одним тредом gunicorn
- **THEN** используется одно и то же соединение к Postgres — новый backend-процесс не форкается на каждый запрос

#### Scenario: Stale connections recovered
- **WHEN** персистентное соединение разорвано (рестарт БД, обрыв сети)
- **THEN** health check обнаруживает это перед использованием и соединение открывается заново, запрос не падает

### Requirement: Environment variables
Все секреты и конфигурация SHALL передаваться через environment variables.

#### Scenario: Required variables defined
- **WHEN** приложение запускается на Render
- **THEN** доступны переменные: SECRET_KEY, DATABASE_URL, DJANGO_ALLOWED_HOSTS

#### Scenario: Debug mode disabled
- **WHEN** приложение работает в production
- **THEN** DEBUG=0

### Requirement: Static files serving
Статические файлы SHALL раздаваться через Whitenoise с manifest-хранилищем
(`CompressedManifestStaticFilesStorage`): имена файлов фингерпринтятся хешем содержимого,
и захешированные ассеты отдаются с долгоживущими immutable-заголовками кэширования,
пригодными для кэша браузера и Cloudflare edge.

#### Scenario: Static files collected
- **WHEN** выполняется collectstatic
- **THEN** файлы собираются в STATIC_ROOT с манифестом соответствия имён и
  захешированными копиями

#### Scenario: Hashed assets served immutable
- **WHEN** браузер запрашивает захешированный ассет (например `main.<hash>.css`)
- **THEN** Whitenoise отдаёт его с `Cache-Control: max-age=31536000, immutable`

#### Scenario: Dangling static references fail at deploy
- **WHEN** шаблон или CSS ссылается на несуществующий статический файл
- **THEN** collectstatic завершается ошибкой на этапе деплоя (entrypoint), а не отдаёт
  битую ссылку в рантайме

### Requirement: Abuse-prevention environment variables

The Render web service SHALL provide the following environment variables consumed by the registration abuse defenses (see [registration-abuse-defenses](../registration-abuse-defenses/spec.md)).

| Variable | Source | Notes |
|---|---|---|
| `CLOUDFLARE_TRUSTED` | `value: "True"` (production behind Cloudflare) | Gates `CloudflareIPMiddleware` reading `HTTP_CF_CONNECTING_IP`. MUST be False on any deployment not behind Cloudflare or the header is spoofable |
| `REGISTRATION_RATE_LIMIT_HOUR` | `value: "3"` | Per-IP hourly limit on POST `/accounts/register/` |
| `REGISTRATION_RATE_LIMIT_DAY` | `value: "10"` | Per-IP daily limit |
| `REDIS_URL` | `fromService: type=redis name=mapsurvey-redis property=connectionString` | Reuses the existing Redis service. Used by `CACHES["default"]` for rate-limit counters |

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

### Requirement: Media object storage environment variables

The Blueprint SHALL supply every service that reads or writes media with the variables needed to reach
the bucket: the enable flag, the bucket name, the bucket Region and the access credentials. Services
that touch no media SHALL NOT carry them. Credentials SHALL be declared as secrets, never as literal
values in `render.yaml`.

#### Scenario: Media variables present wherever files are written

- **WHEN** the web service or the Celery worker starts
- **THEN** the media bucket variables are present in its environment
- **AND** the credentials arrive as secrets rather than Blueprint literals

#### Scenario: A service that writes no media carries no bucket credentials

- **WHEN** a scheduled job that only reads and writes database rows starts
- **THEN** no media bucket credentials are present in its environment

#### Scenario: Preview environments get their own prefix

- **WHEN** Render creates a PR preview from the Blueprint
- **THEN** the preview's media prefix differs from the production prefix
- **AND** the prefix is derived per environment rather than declared in the Blueprint, which cannot
  know a preview service's name in advance
- **AND** the preview uses the same bucket

#### Scenario: Public repository holds no credentials

- **WHEN** `render.yaml` is read from the public repository
- **THEN** it contains no access key id and no secret access key

### Requirement: The web service mounts no disk

The web service SHALL NOT declare a persistent disk. Uploaded media lives in object storage, so no
service needs storage that attaches to a single instance.

#### Scenario: Blueprint declares no disk

- **WHEN** the Blueprint is applied
- **THEN** the web service has no `disk:` block
- **AND** no mount path is reserved for media

#### Scenario: More than one instance can serve

- **WHEN** the web service is scaled to more than one instance
- **THEN** every instance serves the same media
- **AND** no instance holds a file the others cannot see

### Requirement: Help site static service
`render.yaml` SHALL declare a static site service `mapsurvey-help` with `rootDir: help`, a build command that installs dependencies and builds the Starlight project, `staticPublishPath: dist`, a `buildFilter` limited to `help/**`, a pinned `NODE_VERSION`, and `PUBLIC_POSTHOG_KEY` / `PUBLIC_POSTHOG_HOST` as `sync: false` variables. The service SHALL serve `help.mapsurvey.org` (custom domain added in the dashboard).

#### Scenario: Help-only change builds only the help site
- **WHEN** a commit touches files under `help/` only
- **THEN** the `mapsurvey-help` service redeploys and the Django web, worker and cron services do not

#### Scenario: Django-only change leaves the help site alone
- **WHEN** a commit touches no file under `help/`
- **THEN** the `mapsurvey-help` service does not redeploy

### Requirement: Help site has no preview environments
The `mapsurvey-help` service SHALL set `previews.generation: off`; help-site changes are reviewed locally (`npm run dev`) and reach production on merge. A build that nevertheless runs with `IS_PULL_REQUEST=true` SHALL mark every page `noindex`.

#### Scenario: Pull request builds nothing for the help site
- **WHEN** a pull request changes a file under `help/`
- **THEN** no preview of `mapsurvey-help` is created

### Requirement: Production error logging
Необработанные исключения (HTTP 500) SHALL логироваться с полным трейсбеком в stdout
контейнера, чтобы попадать в Render logs. Конфигурация LOGGING SHALL включать root-логгер
с console-хендлером уровня WARNING, не нарушая существующую маршрутизацию `abuse.*`.

#### Scenario: Unhandled exception traceback reaches Render logs
- **WHEN** view выбрасывает необработанное исключение при DEBUG=0
- **THEN** полный трейсбек появляется в stdout контейнера (Render app logs)

#### Scenario: Abuse logger routing preserved
- **WHEN** модуль survey/abuse.py пишет в логгер `abuse.*`
- **THEN** записи форматируются и маршрутизируются как до изменения

### Requirement: Web workers are recycled
Gunicorn SHALL restart each worker after a bounded number of requests
(`--max-requests` with `--max-requests-jitter`), with both numbers tunable through
environment variables declared in `render.yaml`, so that allocator fragmentation left by
large requests cannot accumulate for the life of the process.

#### Scenario: Worker recycles without dropping requests
- **WHEN** a worker reaches its request budget
- **THEN** it finishes its in-flight requests, exits, and the master has already started its replacement

#### Scenario: Budget tunable without rebuild
- **WHEN** an operator sets `GUNICORN_MAX_REQUESTS` or `GUNICORN_MAX_REQUESTS_JITTER` in the Render dashboard and restarts the service
- **THEN** gunicorn applies the new budget without an image rebuild

#### Scenario: Recycling and shutdown answer every accepted connection
- **WHEN** a worker leaves — its request budget is spent, or the master received a deploy's SIGTERM — while connections it has accepted are still unread or in flight
- **THEN** it stops accepting new connections first and answers every connection it already holds before exiting, so no request is reset (`scripts/gunicorn_recycle_check.py` shows zero failures over keep-alive, fresh-connection and SIGTERM runs)

### Requirement: Web service plan
The production web service SHALL run on a Render plan with at least 2 GB of memory
(`standard`), and that plan SHALL be declared in `render.yaml` rather than set in the
dashboard, because a Blueprint sync overwrites a dashboard-only plan. PR preview web
services SHALL stay on `starter` through `previewPlan`.

#### Scenario: Production web service has 2 GB
- **WHEN** the Blueprint is applied
- **THEN** the `mapsurvey` web service runs on the `standard` plan with a 2 GB memory limit

#### Scenario: Dashboard changes do not drift from the Blueprint
- **WHEN** an operator changes the web service plan in the Render dashboard only
- **THEN** the next Blueprint sync restores the plan declared in `render.yaml`
- **AND** therefore every plan change is made in `render.yaml`

#### Scenario: Previews stay on the small plan
- **WHEN** Render creates a PR preview from the Blueprint
- **THEN** the preview web service runs on `starter`

### Requirement: Database plan
The production database SHALL run on a Render plan with at least 1 GB of memory
(`basic-1gb`), declared in `render.yaml` rather than set in the dashboard, because a
Blueprint sync overwrites a dashboard-only plan. PR preview databases SHALL stay on
`basic-256mb` through `previewPlan`.

#### Scenario: Production database has 1 GB
- **WHEN** the Blueprint is applied
- **THEN** `mapsurvey-db` runs on the `basic-1gb` plan with a 1 GB memory limit

#### Scenario: Previews stay on the small plan
- **WHEN** Render creates a PR preview from the Blueprint
- **THEN** the preview database runs on `basic-256mb`

### Requirement: Runtime versions are supported upstream
The Docker image SHALL run a CPython release inside its upstream security-support window
and a Django LTS release inside its extended-support window, and both SHALL be pinned
explicitly (`Dockerfile` base image; `Pipfile` `python_version` and a `~=` Django pin) so
that dependency resolution cannot re-pin an end-of-life Django silently. The lock file
SHALL be generated under the same Python the image runs.

#### Scenario: Image runs supported versions
- **WHEN** the production image is built from the Blueprint
- **THEN** it runs Python 3.12 and Django 5.2 LTS

#### Scenario: Resolver cannot drift to an unsupported Django
- **WHEN** `pipenv lock` is run
- **THEN** the resolved Django stays within the pinned LTS series regardless of what newer major versions exist

#### Scenario: Respondent pages render unchanged after the upgrade
- **WHEN** a section page of a published survey is rendered
- **THEN** every question is a question card built by the project's own templates and widgets, and no respondent-facing template delegates to Django's form-level template, whose markup changed in 5.0

