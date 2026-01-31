# Demo Survey Structure

Демонстрационный опрос, показывающий все возможности платформы Mapsurvey.

---

## Survey Header

| Поле | Значение |
|------|----------|
| Name | `demo-survey` |
| Title | Demo Survey: Все возможности платформы |
| Description | Этот опрос демонстрирует все типы вопросов и функции Mapsurvey |
| Active | Yes |

---

## Option Groups (переиспользуемые наборы выбора)

### 1. Satisfaction Scale
| Value | Label |
|-------|-------|
| 1 | Очень плохо |
| 2 | Плохо |
| 3 | Нормально |
| 4 | Хорошо |
| 5 | Отлично |

### 2. Yes/No
| Value | Label |
|-------|-------|
| yes | Да |
| no | Нет |

### 3. Transport Types
| Value | Label |
|-------|-------|
| walk | Пешком |
| bike | Велосипед |
| public | Общественный транспорт |
| car | Автомобиль |
| other | Другое |

### 4. Age Groups
| Value | Label |
|-------|-------|
| 18-24 | 18-24 года |
| 25-34 | 25-34 года |
| 35-44 | 35-44 года |
| 45-54 | 45-54 года |
| 55+ | 55 и старше |

---

## Section 1: Введение

**Map Position**: Центр города (широкий обзор)
**Map Zoom**: 12

| # | Name | Question Text | Type | Required | Option Group | Notes |
|---|------|---------------|------|----------|--------------|-------|
| 1.1 | intro_html | *HTML-блок с приветствием и инструкциями* | `html` | - | - | Информационный блок без ввода |

**HTML Content для 1.1:**
```html
<div class="intro-block">
  <h3>Добро пожаловать!</h3>
  <p>Этот опрос демонстрирует все возможности платформы Mapsurvey.</p>
  <p>Вы увидите различные типы вопросов: текстовые, выбор, карты и другие.</p>
</div>
```

---

## Section 2: Текстовые вопросы

**Map Position**: Скрыта (или минимизирована)

| # | Name | Question Text | Subtext | Type | Required | Notes |
|---|------|---------------|---------|------|----------|-------|
| 2.1 | full_name | Как вас зовут? | Имя и фамилия | `text_line` | Yes | Однострочный текст |
| 2.2 | email | Ваш email | Для связи с вами | `text_line` | No | Опциональное поле |
| 2.3 | feedback | Расскажите о себе | Любая информация, которой хотите поделиться | `text` | No | Многострочный текст |

---

## Section 3: Выбор вариантов

**Map Position**: Скрыта

| # | Name | Question Text | Type | Required | Option Group | Notes |
|---|------|---------------|------|----------|--------------|-------|
| 3.1 | age_group | Ваша возрастная группа | `choice` | Yes | Age Groups | Одиночный выбор (radio) |
| 3.2 | transport | Какой транспорт вы используете? | `multichoice` | Yes | Transport Types | Множественный выбор (checkbox) |
| 3.3 | has_car | У вас есть личный автомобиль? | `choice` | No | Yes/No | Простой да/нет |

---

## Section 4: Шкалы и оценки

**Map Position**: Скрыта

| # | Name | Question Text | Subtext | Type | Required | Option Group | Config |
|---|------|---------------|---------|------|----------|--------------|--------|
| 4.1 | satisfaction | Насколько вы довольны городской инфраструктурой? | | `choice` | Yes | Satisfaction Scale | |
| 4.2 | comfort_range | Оцените комфорт передвижения по городу | 1 = очень неудобно, 10 = очень удобно | `range` | Yes | - | min=1, max=10 |
| 4.3 | rating_stars | Оцените качество дорог | | `rating` | No | - | max=5 (звёзды) |

---

## Section 5: Дата и время

**Map Position**: Скрыта

| # | Name | Question Text | Subtext | Type | Required | Notes |
|---|------|---------------|---------|------|----------|-------|
| 5.1 | visit_date | Когда вы последний раз посещали центр города? | Выберите дату и время | `datetime` | No | Календарь + время |

---

## Section 6: Загрузка изображений

**Map Position**: Скрыта

| # | Name | Question Text | Subtext | Type | Required | Notes |
|---|------|---------------|---------|------|----------|-------|
| 6.1 | photo_problem | Загрузите фото проблемного места | Если есть | `image` | No | Загрузка файла |

---

## Section 7: Геолокация - Точки

**Map Position**: Центр города
**Map Zoom**: 14

| # | Name | Question Text | Subtext | Type | Required | Color | Icon |
|---|------|---------------|---------|------|----------|-------|------|
| 7.1 | home_location | Отметьте ваш дом на карте | Приблизительное местоположение | `point` | Yes | #2196F3 | fa-home |
| 7.2 | work_location | Отметьте место работы/учёбы | Если применимо | `point` | No | #4CAF50 | fa-briefcase |
| 7.3 | favorite_place | Отметьте ваше любимое место в городе | | `point` | No | #E91E63 | fa-heart |

---

## Section 8: Геолокация - Линии

**Map Position**: Центр города
**Map Zoom**: 13

| # | Name | Question Text | Subtext | Type | Required | Color |
|---|------|---------------|---------|------|----------|-------|
| 8.1 | commute_route | Нарисуйте ваш обычный маршрут на работу | Линия от дома до работы | `line` | No | #FF5722 |
| 8.2 | walking_route | Нарисуйте маршрут вашей обычной прогулки | Если гуляете регулярно | `line` | No | #9C27B0 |

---

## Section 9: Геолокация - Полигоны

**Map Position**: Центр города
**Map Zoom**: 13

| # | Name | Question Text | Subtext | Type | Required | Color |
|---|------|---------------|---------|------|----------|-------|
| 9.1 | neighborhood | Выделите район, где вы живёте | Примерные границы | `polygon` | Yes | #3F51B5 |
| 9.2 | avoid_area | Выделите районы, которые вы избегаете | Если такие есть | `polygon` | No | #F44336 |

---

## Section 10: Комбинированная секция

**Map Position**: Центр города
**Map Zoom**: 14

Демонстрация смешанных типов вопросов в одной секции.

| # | Name | Question Text | Type | Required | Option Group | Color |
|---|------|---------------|------|----------|--------------|-------|
| 10.1 | problem_point | Отметьте проблемное место | `point` | Yes | - | #F44336 |
| 10.2 | problem_type | Тип проблемы | `choice` | Yes | Problem Types* | - |
| 10.3 | problem_desc | Опишите проблему подробнее | `text` | No | - | - |
| 10.4 | problem_rating | Насколько это критично? | `rating` | Yes | - | - |

*Создать Option Group "Problem Types": дороги, освещение, мусор, безопасность, другое

---

## Section 11: Завершение

**Map Position**: Скрыта

| # | Name | Question Text | Type | Required | Notes |
|---|------|---------------|------|----------|-------|
| 11.1 | final_comments | Дополнительные комментарии | `text` | No | |
| 11.2 | outro_html | *Благодарность за участие* | `html` | - | |

**HTML Content для 11.2:**
```html
<div class="outro-block">
  <h3>Спасибо за участие!</h3>
  <p>Ваши ответы помогут улучшить городскую инфраструктуру.</p>
</div>
```

---

## Демонстрируемые возможности

| Возможность | Где показана |
|-------------|--------------|
| **12 типов вопросов** | Секции 2-9 |
| `html` - информационные блоки | 1.1, 11.2 |
| `text_line` - однострочный текст | 2.1, 2.2 |
| `text` - многострочный текст | 2.3, 10.3 |
| `choice` - одиночный выбор | 3.1, 3.3, 10.2 |
| `multichoice` - множественный выбор | 3.2 |
| `range` - слайдер | 4.2 |
| `rating` - звёзды | 4.3, 10.4 |
| `datetime` - дата/время | 5.1 |
| `image` - загрузка фото | 6.1 |
| `point` - точка на карте | 7.1, 7.2, 7.3, 10.1 |
| `line` - линия на карте | 8.1, 8.2 |
| `polygon` - полигон на карте | 9.1, 9.2 |
| **Option Groups** | Переиспользование в 3.1, 3.2, 3.3, 4.1 |
| **Required/Optional** | Смешаны во всех секциях |
| **Subtext** | Подсказки в 2.x, 4.2, 7.x, 8.x |
| **Color/Icon** | Кастомизация гео-вопросов 7.x |
| **Map positioning** | Разный зум и центр по секциям |
| **Mixed sections** | Секция 10 - разные типы вместе |

---

## Экспорт данных

После сбора ответов, экспорт `/surveys/demo-survey/download` создаст ZIP с:

```
demo-survey-export.zip
├── home_location.geojson      # Точки домов
├── work_location.geojson      # Точки работы
├── favorite_place.geojson     # Любимые места
├── commute_route.geojson      # Маршруты на работу
├── walking_route.geojson      # Прогулочные маршруты
├── neighborhood.geojson       # Районы проживания
├── avoid_area.geojson         # Избегаемые районы
├── problem_point.geojson      # Проблемные точки
└── responses.csv              # Все не-гео ответы
```
