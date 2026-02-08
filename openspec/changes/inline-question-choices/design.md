## Context

Текущая система хранит варианты ответов в трёх таблицах:
- `OptionGroup` — группа вариантов (например, "YesNo", "Satisfaction1-5")
- `OptionChoice` — отдельный вариант с кодом и именем
- `OptionChoiceTranslation` — переводы для каждого варианта

Связи:
- `Question.option_group` (FK) → `OptionGroup`
- `Answer.choice` (M2M) → `OptionChoice`

Проблемы текущего подхода:
- Глобальные группы создают неявные зависимости между опросами
- Сложность при копировании/импорте опросов
- Переводы хранятся отдельно от основных данных
- Избыточная нормализация для простых списков

## Goals / Non-Goals

**Goals:**
- Упростить модель данных, храня варианты прямо в вопросе
- Встроить переводы в структуру данных (без отдельной таблицы)
- Сохранить обратную совместимость формата экспорта (с адаптерами)
- Мигрировать существующие данные без потерь

**Non-Goals:**
- Поддержка "общих" групп вариантов между опросами (убираем эту концепцию)
- Изменение UI/UX заполнения опросов
- Изменение типов вопросов (choice, multichoice, range, rating остаются)

## Decisions

### 1. Формат хранения вариантов в Question

**Решение**: JSONField со структурой:
```python
Question.choices = [
    {"code": 1, "name": {"en": "Never", "ru": "Никогда"}},
    {"code": 2, "name": {"en": "Sometimes", "ru": "Иногда"}},
    ...
]
```

**Альтернативы:**
- Inline модель `QuestionChoice` (FK к Question) — сохраняет реляционную структуру, но добавляет ещё одну таблицу и усложняет сериализацию
- Простой JSON без переводов `[{"code": 1, "name": "Never"}, ...]` — потребовал бы отдельную таблицу/поле для переводов

**Обоснование**: JSONField с переводами внутри — самый компактный формат, не требует JOIN'ов, переводы атомарны с данными.

### 2. Хранение выбранных вариантов в Answer

**Решение**: JSONField со списком кодов:
```python
Answer.selected_choices = [1, 3]  # коды выбранных вариантов
```

**Альтернативы:**
- Хранить имена вариантов `["Never", "Often"]` — ломается при переименовании
- ArrayField(IntegerField) — PostgreSQL-специфично, JSONField универсальнее
- Оставить M2M на новую модель — избыточная сложность

**Обоснование**: Коды стабильны (не меняются при переводах), JSONField работает на всех БД Django.

### 3. Получение имени варианта по языку

**Решение**: Хелпер-метод в Question:
```python
def get_choice_name(self, code: int, lang: str = None) -> str:
    for choice in self.choices or []:
        if choice["code"] == code:
            names = choice["name"]
            if isinstance(names, dict):
                return names.get(lang) or names.get("en") or next(iter(names.values()))
            return names  # fallback для старого формата
    return str(code)
```

**Альтернативы:**
- Отдельный сервис/utility функция — размазывает логику
- Property на Answer — требует знания о Question

### 4. Валидация JSON-структуры

**Решение**: Django validator + JSON Schema:
```python
from django.core.validators import BaseValidator

class ChoicesValidator(BaseValidator):
    def __call__(self, value):
        if not isinstance(value, list):
            raise ValidationError("choices must be a list")
        for item in value:
            if "code" not in item or "name" not in item:
                raise ValidationError("Each choice must have 'code' and 'name'")
```

### 5. Миграция данных

**Решение**: Двухфазная миграция:

1. **Миграция структуры** (добавление новых полей):
   - Добавить `Question.choices` (JSONField, null=True)
   - Добавить `Answer.selected_choices` (JSONField, null=True)

2. **Миграция данных** (data migration):
   ```python
   def migrate_choices(apps, schema_editor):
       Question = apps.get_model('survey', 'Question')
       for q in Question.objects.filter(option_group__isnull=False):
           q.choices = [
               {
                   "code": c.code,
                   "name": {t.language: t.name for t in c.translations.all()} | {"default": c.name}
               }
               for c in q.option_group.choices()
           ]
           q.save()
   ```

3. **Удаление старых полей** (отдельная миграция после проверки):
   - Удалить `Question.option_group`
   - Удалить `Answer.choice`
   - Удалить модели OptionGroup, OptionChoice, OptionChoiceTranslation

### 6. Сериализация структуры (survey.json)

**Решение**: Новый формат без секции `option_groups`:

```json
{
  "questions": [
    {
      "code": "Q001",
      "input_type": "choice",
      "choices": [
        {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
        {"code": 2, "name": {"en": "No", "ru": "Нет"}}
      ]
    }
  ]
}
```

Для обратной совместимости при импорте старого формата:
- Если есть `option_groups` + `option_group_name` в вопросах — конвертировать в inline `choices`

### 7. Экспорт данных ответов (download_data, responses.json)

**Текущее поведение** (views.py:338-397):
```python
# Получение имени через M2M
result = answer.choice.all()[0].name  # single choice
result = [c.name for c in answer.choice.all()]  # multichoice
```

**Новое решение**:
```python
# Получение имени по коду из Question.choices
def get_choice_names(answer, lang=None):
    codes = answer.selected_choices or []
    question = answer.question
    return [question.get_choice_name(code, lang) for code in codes]

# В download_data:
result = get_choice_names(answer, lang)[0]  # single choice
result = get_choice_names(answer, lang)  # multichoice
```

**Формат responses.json** остаётся совместимым:
```json
{
  "answers": [
    {
      "question_code": "Q001",
      "choices": ["Yes", "Maybe"]  // имена, не коды - для читаемости
    }
  ]
}
```

**При импорте ответов**: конвертировать имена обратно в коды через поиск в `Question.choices`

## Risks / Trade-offs

**[Потеря переиспользования групп]** → Приемлемо: на практике группы редко переиспользовались между опросами, а копирование опроса теперь атомарно копирует и варианты.

**[Больший размер JSON в БД]** → Незначительно: даже 20 вариантов × 3 языка — это ~2KB на вопрос.

**[Миграция существующих данных]** → Mitigation: двухфазная миграция с возможностью отката. Сначала добавляем новые поля, копируем данные, проверяем, затем удаляем старые.

**[Изменение формата экспорта]** → Mitigation: поддержка импорта старого формата через конвертер, версионирование формата.

**[Невозможность JOIN по вариантам]** → Приемлемо: агрегация по вариантам редко нужна, при необходимости можно использовать JSON-функции PostgreSQL.

## Migration Plan

1. Создать миграцию с новыми полями (не удаляя старые)
2. Запустить data migration для копирования данных
3. Обновить код (views, forms, serialization) для работы с новыми полями
4. Тестирование на staging
5. Deploy + финальная миграция удаления старых таблиц
6. Rollback: если проблемы — откатить код, данные в старых полях сохранены

## Open Questions

- Нужна ли поддержка "default" языка отдельно от конкретных языков, или использовать первый доступный?
- Оставлять ли `Answer.selected_choices` как `null` для вопросов без вариантов, или использовать пустой список `[]`?
