## 1. Подготовка Django для production

- [x] 1.1 Добавить dj-database-url в зависимости для парсинга DATABASE_URL
- [x] 1.2 Обновить settings.py для поддержки DATABASE_URL
- [x] 1.3 Добавить RENDER_EXTERNAL_HOSTNAME в ALLOWED_HOSTS

## 2. Конфигурация Render

- [x] 2.1 Создать render.yaml с Web Service (Docker, Starter tier)
- [x] 2.2 Добавить PostgreSQL database в render.yaml (Starter tier)
- [x] 2.3 Настроить environment variables в render.yaml

## 3. Адаптация Docker

- [x] 3.1 Обновить entrypoint.sh для работы с DATABASE_URL
- [x] 3.2 Добавить поддержку переменной PORT для Gunicorn

## 4. Деплой и проверка

- [x] 4.1 Подключить репозиторий к Render через Dashboard или API
- [ ] 4.2 Включить PostGIS расширение в базе данных
- [ ] 4.3 Проверить работу приложения на Render URL
