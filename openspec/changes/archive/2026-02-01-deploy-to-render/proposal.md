## Why

Приложение Mapsurvey сейчас работает только локально через Docker Compose. Нужен production-ready деплой на облачную платформу Render для публичного доступа к геоопросам.

## What Changes

- Создание `render.yaml` (Blueprint) для декларативной конфигурации инфраструктуры
- Настройка Web Service для Django-приложения с Gunicorn
- Настройка PostgreSQL с PostGIS расширением на Render
- Конфигурация environment variables для production
- Адаптация Dockerfile/build process под требования Render
- Настройка статических файлов через Whitenoise (уже частично готово)

## Capabilities

### New Capabilities
- `render-deployment`: Конфигурация и скрипты для деплоя на Render (render.yaml, build scripts)

### Modified Capabilities
<!-- Нет существующих спецификаций для модификации -->

## Impact

**Код:**
- `render.yaml` - новый файл Blueprint
- `build.sh` - скрипт сборки для Render (опционально)
- Возможные изменения в `settings.py` для production-настроек

**Зависимости:**
- Render PostgreSQL с PostGIS
- Render Web Service (Docker или Native)

**Инфраструктура:**
- Новые сервисы в Render Dashboard
- Environment variables в Render
- База данных PostGIS на Render

**API/URLs:**
- Новый публичный URL на `*.onrender.com`
- Обновление `DJANGO_ALLOWED_HOSTS`
