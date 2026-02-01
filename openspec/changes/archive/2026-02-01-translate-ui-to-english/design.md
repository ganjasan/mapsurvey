## Context

Django-приложение Mapsurvey использует PostGIS для геоопросов. Интерфейс содержит ~41 захардкоженную русскую строку в HTML-шаблонах и JavaScript (Leaflet.draw).

Django i18n уже включён (`USE_I18N = True`), но не используется — строки не обёрнуты в `{% trans %}`. Нужно внедрить i18n-инфраструктуру с английским языком по умолчанию и сохранением русского для совместимости.

**Текущее состояние:**
- `LANGUAGE_CODE = 'ru-RU'` в settings.py
- `gettext_lazy` импортирован в models.py, но не используется в шаблонах
- JavaScript-строки (Leaflet.draw tooltips) захардкожены в `base_survey_template.html`

## Goals / Non-Goals

**Goals:**
- Перевести весь user-facing интерфейс на английский
- Создать i18n-инфраструктуру для будущих языков
- Английский — язык по умолчанию
- Сохранить русский перевод для обратной совместимости

**Non-Goals:**
- Автоматическое определение языка пользователя (будет добавлено позже)
- Перевод админки Django
- Перевод комментариев в коде
- UI для переключения языков

## Decisions

### 1. Передача переводов в JavaScript

**Решение:** JSON-объект в data-атрибуте `<body>` + парсинг в JS

**Альтернативы:**
- Отдельный API endpoint — избыточно для статических строк
- Inline `<script>` с переменными — проблемы с CSP
- Отдельный .js файл с переводами — лишний HTTP-запрос

**Реализация:**
```html
<!-- base_survey_template.html -->
<body data-i18n='{% i18n_json %}'>
```
```javascript
const i18n = JSON.parse(document.body.dataset.i18n);
// Использование: i18n.startDrawing, i18n.clickToPlaceMarker
```

### 2. Структура locale-директории

**Решение:** `survey/locale/{lang}/LC_MESSAGES/django.po`

```
survey/
└── locale/
    ├── en/
    │   └── LC_MESSAGES/
    │       └── django.po
    └── ru/
        └── LC_MESSAGES/
            └── django.po
```

### 3. Обработка Leaflet.draw локализации

**Решение:** Переопределить `L.drawLocal` объект через переданные i18n-строки

```javascript
L.drawLocal.draw.handlers.marker.tooltip.start = i18n.clickToPlaceMarker;
L.drawLocal.draw.handlers.polygon.tooltip.start = i18n.clickToStartShape;
// ... и т.д.
```

### 4. Язык по умолчанию

**Решение:** `LANGUAGE_CODE = 'en-us'` в settings.py

Русский остаётся доступным через файлы переводов, но английский — primary.

## Risks / Trade-offs

**[Дублирование строк в шаблонах навигации]** → Кнопки "Назад/Далее/Завершить" повторяются в 4 шаблонах. Это не блокер для i18n, но можно вынести в include.

**[Синхронизация JS и Django переводов]** → JS-строки должны соответствовать Django `.po` файлам. Митигация: кастомный template tag `{% i18n_json %}` генерирует JSON из тех же источников.

**[Email-шаблоны]** → `.txt` файлы требуют `{% load i18n %}` в начале. Нужно проверить, что email-отправка корректно рендерит шаблоны.
