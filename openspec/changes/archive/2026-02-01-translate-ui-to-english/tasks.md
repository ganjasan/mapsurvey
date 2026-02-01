## 1. Django Settings Configuration

- [x] 1.1 Change `LANGUAGE_CODE` from `ru-RU` to `en-us` in `mapsurvey/settings.py`
- [x] 1.2 Add `LOCALE_PATHS` setting pointing to `survey/locale/`
- [x] 1.3 Create locale directory structure: `survey/locale/en/LC_MESSAGES/` and `survey/locale/ru/LC_MESSAGES/`

## 2. Custom Template Tag for JavaScript i18n

- [x] 2.1 Create `survey/templatetags/i18n_extras.py` with `{% i18n_json %}` tag
- [x] 2.2 Define all JS translation keys (startDrawing, clickToPlaceMarker, etc.) in the tag
- [x] 2.3 Register the template tag library

## 3. Survey Navigation Templates

- [x] 3.1 Add `{% load i18n %}` to `survey_section.html` and wrap "Назад", "Далее", "Завершить" with `{% trans %}`
- [x] 3.2 Add `{% load i18n %}` to `survey_header.html` and wrap "Начать" with `{% trans %}`
- [x] 3.3 Add `{% load i18n %}` to `survey_header_template.html` and wrap navigation buttons
- [x] 3.4 Add `{% load i18n %}` to `survey_section_block.html` and wrap navigation buttons

## 4. Map Drawing Interface (Leaflet.draw)

- [x] 4.1 Add `{% load i18n_extras %}` and `data-i18n='{% i18n_json %}'` to `<body>` in `base_survey_template.html`
- [x] 4.2 Add JavaScript to parse `document.body.dataset.i18n` at page load
- [x] 4.3 Replace hardcoded Russian strings in `L.drawLocal` with i18n values
- [x] 4.4 Update "Начать рисовать", "Завершить редактировать", "Удалить" button labels to use i18n

## 5. Registration Templates

- [x] 5.1 Add `{% load i18n %}` and `{% trans %}` to `django_registration/registration_complete.html`
- [x] 5.2 Add `{% load i18n %}` and `{% trans %}` to `django_registration/activation_complete.html`
- [x] 5.3 Add `{% load i18n %}` and `{% trans %}` to `django_registration/activation_failed.html`

## 6. Email Templates

- [x] 6.1 Add `{% load i18n %}` and `{% trans %}` to `django_registration/activation_email_subject.txt`
- [x] 6.2 Add `{% load i18n %}` and `{% blocktrans %}` to `django_registration/activation_email_body.txt`

## 7. Translation Files

- [x] 7.1 Run `python manage.py makemessages -l en` to generate English .po file
- [x] 7.2 Run `python manage.py makemessages -l ru` to generate Russian .po file
- [x] 7.3 Fill in English translations in `survey/locale/en/LC_MESSAGES/django.po`
- [x] 7.4 Fill in Russian translations in `survey/locale/ru/LC_MESSAGES/django.po`
- [x] 7.5 Run `python manage.py compilemessages` to generate .mo files

## 8. Verification

- [x] 8.1 Test survey navigation buttons display in English
- [x] 8.2 Test map drawing tooltips display in English
- [x] 8.3 Test registration flow displays in English
- [x] 8.4 Verify Russian translations load when locale is changed
