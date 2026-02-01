## Why

Интерфейс приложения содержит ~41 русскую строку (кнопки, подсказки, сообщения об ошибках), что ограничивает использование продукта англоязычными пользователями. Django i18n уже настроен (`USE_I18N = True`), но не используется — строки захардкожены в шаблонах и JavaScript.

## What Changes

- Внедрение Django i18n для всех user-facing строк
- Обёртка строк в шаблонах через `{% trans %}` / `{% blocktrans %}`
- Создание механизма передачи переводов в JavaScript (для Leaflet.draw)
- Создание файлов переводов (`locale/en/LC_MESSAGES/django.po`)
- Изменение `LANGUAGE_CODE` с `ru-RU` на `en-us` по умолчанию
- Перевод 41 строки на английский язык

### Строки для перевода

| Категория | Кол-во | Файлы |
|-----------|--------|-------|
| Кнопки навигации | 12 | `survey_section.html`, `survey_header.html`, `survey_header_template.html`, `survey_section_block.html` |
| Интерфейс карты (Leaflet) | 13 | `base_survey_template.html` (JavaScript) |
| Регистрация/активация | 14 | `django_registration/*.html` |
| Email шаблоны | 3 | `activation_email_*.txt` |

## Capabilities

### New Capabilities
- `ui-internationalization`: Инфраструктура i18n — настройка Django, структура locale, механизм передачи переводов в JS

### Modified Capabilities
- нет (только добавление i18n обёрток к существующему коду)

## Impact

**Код:**
- `mapsurvey/settings.py` — настройки языка, LOCALE_PATHS
- `survey/templates/*.html` — добавление `{% load i18n %}` и `{% trans %}`
- `survey/templates/base_survey_template.html` — рефакторинг JS для приёма переводов

**Новые файлы:**
- `survey/locale/en/LC_MESSAGES/django.po` — переводы на английский
- `survey/locale/ru/LC_MESSAGES/django.po` — русский (для обратной совместимости)

**Зависимости:**
- Нет новых зависимостей (Django i18n встроен)

**Миграции:**
- Не требуются
