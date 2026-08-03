# render-deployment — delta for web-concurrency

## MODIFIED Requirements

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

## ADDED Requirements

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
