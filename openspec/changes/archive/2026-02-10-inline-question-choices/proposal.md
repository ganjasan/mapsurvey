## Why

Текущая архитектура хранит варианты ответов (choices) в отдельных таблицах `OptionGroup` и `OptionChoice`, что создаёт избыточную сложность. Для каждого опроса логичнее хранить варианты непосредственно в вопросе, упрощая модель данных и устраняя необходимость управления глобальными группами опций.

## What Changes

- **BREAKING**: Удаление моделей `OptionGroup`, `OptionChoice`, `OptionChoiceTranslation`
- **BREAKING**: Замена `Question.option_group` (FK) на `Question.choices` (JSONField)
- **BREAKING**: Замена `Answer.choice` (M2M) на `Answer.selected_choices` (JSONField со списком кодов)
- Новый формат хранения вариантов с встроенной поддержкой переводов:
  ```json
  [
    {"code": 1, "name": {"en": "Never", "ru": "Никогда"}},
    {"code": 2, "name": {"en": "Sometimes", "ru": "Иногда"}}
  ]
  ```
- Обновление форм для генерации полей из JSONField
- Обновление сериализации для нового формата экспорта/импорта
- Миграция существующих данных

## Capabilities

### New Capabilities

- `inline-choices`: Хранение вариантов ответов непосредственно в модели Question как JSONField с поддержкой мультиязычности

### Modified Capabilities

- `survey-serialization`: Изменение формата экспорта/импорта — варианты теперь часть вопроса, а не отдельная секция option_groups

## Impact

**Модели** (survey/models.py):
- Удаление: OptionGroup, OptionChoice, OptionChoiceTranslation (строки 169-217)
- Изменение: Question.option_group → Question.choices
- Изменение: Answer.choice → Answer.selected_choices

**Views** (survey/views.py):
- survey_section(): логика сохранения ответов (строки 218-257)
- download_data(): экспорт выбранных вариантов (строки 338-397)

**Forms** (survey/forms.py):
- _get_form_from_input_type(): генерация choice/multichoice/range/rating полей (строки 146-182)

**Admin** (survey/admin.py):
- Удаление OptionGroup/OptionChoice admin
- Обновление QuestionInLine для редактирования choices

**Serialization** (survey/serialization.py):
- serialize_option_groups() → убрать
- get_or_create_option_groups() → убрать
- link_choices() → переписать
- Обновить формат survey.json

**Tests** (survey/tests.py):
- ~20 тестов используют OptionGroup/OptionChoice — требуют обновления

**Миграции**:
- Данные из OptionChoice нужно мигрировать в Question.choices
- Данные из Answer.choice M2M нужно мигрировать в Answer.selected_choices
