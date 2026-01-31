## ADDED Requirements

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
