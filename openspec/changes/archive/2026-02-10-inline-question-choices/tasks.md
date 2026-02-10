## 1. Models - Добавление новых полей

- [x] 1.1 Добавить `Question.choices` JSONField (null=True, blank=True)
- [x] 1.2 Добавить `Answer.selected_choices` JSONField (null=True, blank=True)
- [x] 1.3 Создать ChoicesValidator для валидации структуры JSON
- [x] 1.4 Добавить метод `Question.get_choice_name(code, lang)` с fallback логикой
- [x] 1.5 Добавить хелпер-функцию `get_selected_choice_names(answer, lang)`

## 2. Миграции

- [x] 2.1 Создать миграцию для добавления новых полей (Question.choices, Answer.selected_choices)
- [x] 2.2 Создать data migration для копирования OptionGroup/OptionChoice в Question.choices
- [x] 2.3 Создать data migration для копирования Answer.choice M2M в Answer.selected_choices

## 3. Forms - Генерация полей

- [x] 3.1 Обновить `_get_form_from_input_type()` для choice: читать из question.choices вместо option_group
- [x] 3.2 Обновить `_get_form_from_input_type()` для multichoice: читать из question.choices
- [x] 3.3 Обновить `_get_form_from_input_type()` для range: вычислять min/max из question.choices
- [x] 3.4 Обновить `_get_form_from_input_type()` для rating: читать из question.choices
- [x] 3.5 Обновить получение переведённых labels через question.get_choice_name()

## 4. Views - Сохранение и отображение ответов

- [x] 4.1 Обновить `survey_section()`: сохранять коды в answer.selected_choices вместо M2M
- [x] 4.2 Обновить `survey_section()` для sub-questions: аналогичное изменение
- [x] 4.3 Обновить `download_data()`: получать имена через get_selected_choice_names()
- [x] 4.4 Обновить GeoJSON экспорт sub-questions: использовать новый формат

## 5. Serialization - Экспорт структуры

- [x] 5.1 Удалить функцию `serialize_option_groups()`
- [x] 5.2 Обновить `_serialize_question()`: добавить поле choices из question.choices
- [x] 5.3 Удалить поле `option_group_name` из сериализации вопроса
- [x] 5.4 Обновить `serialize_survey_to_dict()`: убрать секцию option_groups

## 6. Serialization - Экспорт данных

- [x] 6.1 Обновить `serialize_choices()`: читать из answer.selected_choices и question.choices
- [x] 6.2 Обновить `_serialize_answer()`: использовать новый serialize_choices()

## 7. Serialization - Импорт структуры

- [x] 7.1 Обновить `_create_question()`: читать choices из JSON и сохранять в Question.choices
- [x] 7.2 Добавить конвертер legacy формата: option_groups + option_group_name → inline choices
- [x] 7.3 Обновить валидацию: требовать choices для choice/multichoice/range/rating
- [x] 7.4 Удалить вызов `get_or_create_option_groups()`
- [x] 7.5 Удалить функцию `get_or_create_option_groups()`

## 8. Serialization - Импорт данных

- [x] 8.1 Обновить `link_choices()`: конвертировать имена в коды через Question.choices
- [x] 8.2 Сохранять коды в Answer.selected_choices вместо M2M

## 9. Admin

- [x] 9.1 Удалить OptionGroup из admin.site.register
- [x] 9.2 Удалить OptionChoice и OptionChoiceAdmin
- [x] 9.3 Удалить OptionChoiceTranslationInline
- [x] 9.4 Убрать option_group из QuestionInLine.fields
- [x] 9.5 Добавить choices в QuestionInLine.fields (JSON виджет)

## 10. Tests - Обновление существующих тестов

- [x] 10.1 Обновить setUp методы: создавать question.choices вместо OptionGroup/OptionChoice
- [x] 10.2 Обновить тесты сериализации структуры
- [x] 10.3 Обновить тесты сериализации данных
- [x] 10.4 Обновить тесты импорта
- [x] 10.5 Добавить тест импорта legacy формата с option_groups
- [x] 10.6 Обновить тесты мультиязычности

## 11. Tests - Новые тесты для inline-choices

- [x] 11.1 Тест Question.get_choice_name() с разными языками
- [x] 11.2 Тест Question.get_choice_name() fallback логики
- [x] 11.3 Тест ChoicesValidator с валидными/невалидными данными
- [x] 11.4 Тест сохранения answer.selected_choices через форму

## 12. Cleanup - Удаление старого кода

- [x] 12.1 Создать финальную миграцию: удалить Question.option_group FK
- [x] 12.2 Создать финальную миграцию: удалить Answer.choice M2M
- [x] 12.3 Удалить модели OptionGroup, OptionChoice, OptionChoiceTranslation
- [x] 12.4 Удалить импорты старых моделей из всех файлов
- [x] 12.5 Удалить методы OptionGroup.choices() и OptionChoice.get_translated_name()
