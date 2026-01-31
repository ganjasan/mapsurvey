## Context

Mapsurvey — Django/GeoDjango приложение для создания геоопросов. Сейчас работает локально через Docker Compose с PostGIS. Нужен production-деплой на Render.

**Текущее состояние:**
- Docker-based сборка (python:3.9-slim + geodeps)
- PostGIS база данных
- Gunicorn как WSGI-сервер
- Whitenoise для статики (настроен)
- Environment variables через .env

**Ограничения Render:**
- PostgreSQL есть, но PostGIS требует отдельной активации
- Docker deployment поддерживается
- Бесплатный tier имеет ограничения (spin down после 15 мин неактивности)

## Goals / Non-Goals

**Goals:**
- Задеплоить работающее приложение на Render
- Настроить PostgreSQL с PostGIS
- Конфигурация через render.yaml (Infrastructure as Code)
- Production-ready настройки (DEBUG=0, секреты)

**Non-Goals:**
- Custom domain (можно добавить позже)
- CI/CD pipeline (Render автоматически деплоит из GitHub)
- Масштабирование и High Availability
- S3 для статики (используем Whitenoise)

## Decisions

### 1. Способ деплоя: Docker vs Native Runtime

**Решение:** Docker

**Причина:** Проект уже имеет рабочий Dockerfile с установленными геобиблиотеками (GDAL, PROJ, etc.). Native Python runtime на Render потребует сложной настройки buildpacks для geodeps.

**Альтернатива:** Native с buildpacks — отклонено из-за сложности настройки геозависимостей.

### 2. База данных: Render PostgreSQL + PostGIS

**Решение:** Использовать Render PostgreSQL и включить PostGIS расширение через миграцию или вручную.

**Причина:** Render PostgreSQL поддерживает PostGIS, нужно только выполнить `CREATE EXTENSION postgis;`

**Альтернатива:** External DB (Supabase, Neon) — отклонено, проще использовать интегрированное решение.

### 3. Статические файлы: Whitenoise

**Решение:** Whitenoise (уже настроен в settings.py)

**Причина:** Простота, не требует дополнительной инфраструктуры. Для текущей нагрузки достаточно.

### 4. Конфигурация: render.yaml Blueprint

**Решение:** Использовать render.yaml для декларативной конфигурации.

**Причина:** Infrastructure as Code, воспроизводимость, версионирование.

## Risks / Trade-offs

**[Starter tier]** → Платный план, приложение не засыпает. Стоимость ~$7/месяц за web service + ~$7/месяц за PostgreSQL.

**[PostGIS расширение]** → Нужно вручную активировать в базе.
*Mitigation:* Добавить миграцию или документировать шаг в README.

**[Секреты в render.yaml]** → Нельзя хранить секреты в файле.
*Mitigation:* Использовать `sync: false` для секретов, задавать через Dashboard.

## Migration Plan

1. Создать render.yaml с конфигурацией сервисов
2. Подключить репозиторий к Render
3. Создать PostgreSQL database
4. Включить PostGIS расширение
5. Задать environment variables (SECRET_KEY, etc.)
6. Деплой и проверка
7. Создать superuser через Render Shell

**Rollback:** Удалить сервисы в Render Dashboard, локальная версия продолжит работать.
