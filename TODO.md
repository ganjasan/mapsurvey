# TODO

## Completed

- [x] Survey Import/Export (2026-02-01)
  - CLI: `export_survey`, `import_survey`
  - Web UI: Export dropdown, Import modal
  - Archived: `openspec/changes/archive/2026-02-01-survey-import-export/`

## Features
- [ ] Надо попробовать создать точную копию Let's try this out from https://www.partimap.eu/en, https://k-monitor.hu/technology

- [ ] Add user geolocation tracking with survey responses
  - Use browser Geolocation API to get user coordinates
  - Request permission and handle denial/unavailability
  - Store location with SurveySession or Answer model
  - Send coordinates when submitting survey forms

- [ ] Multi-language survey support
  - Allow surveys to have translations for different languages
  - Language selection for respondents
  - Translate questions, sections, and option choices

## Editor

- [ ] Кнопка «Посмотреть опрос» в редакторе
  - Добавить кнопку для перехода на публичную страницу опроса из редактора

- [x] Выгрузка данных по старым версиям опроса из интерфейса 16.02.26
  - Dropdown в дашборде с выбором версии (All Versions, Current, v1, v2...)
  - Prefetch archived versions для избежания N+1

- [x] Implement Delete Survey button in `/editor/` 01.02.26
  - Add `delete_survey` view with confirmation
  - Add URL route `/editor/delete/<name>/`
  - Update template with working link and confirmation modal

## Bugs

- [x] 01.02.26 Кривая вёрстка Geo Questions
  - Иконка вопроса налезает на текст
  - Текст subtext обтекает иконку некорректно
  - Нужно исправить CSS для `.geo-question` или аналогичного класса

- [x] Пароль на опросе не работает
  - Тестовый опрос публично доступен любому пользователю
  - Парольная защита не блокирует доступ к опросу

- [ ] Тестовые ответы должны быть помечены и легко удаляемы
  - Ответы, собранные в режиме тестирования, должны быть помечены
  - Должна быть возможность удалить все тестовые ответы перед публикацией

- [ ] Не отображаются иконки в браузере Opera

- [ ] Slider (range input) отображается без рисок
  - Добавить tick marks для визуализации значений

- [x] 01.02.26 Кнопки управления гео-объектами (save/edit/delete) отображаются вертикально
  - Должны быть горизонтально в одну строку
  - Поведение нестабильное: иногда горизонтально, иногда вертикально
  - Зависит от ширины popup или количества sub-questions
  - Leaflet Draw popup toolbar CSS fix
