# TODO

## Completed

- [x] Survey Import/Export (2026-02-01)
  - CLI: `export_survey`, `import_survey`
  - Web UI: Export dropdown, Import modal
  - Archived: `openspec/changes/archive/2026-02-01-survey-import-export/`

## Features

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

- [x] Implement Delete Survey button in `/editor/` 01.02.26
  - Add `delete_survey` view with confirmation
  - Add URL route `/editor/delete/<name>/`
  - Update template with working link and confirmation modal

## Bugs

- [x] 01.02.26 Кривая вёрстка Geo Questions
  - Иконка вопроса налезает на текст
  - Текст subtext обтекает иконку некорректно
  - Нужно исправить CSS для `.geo-question` или аналогичного класса

- [ ] Slider (range input) отображается без рисок
  - Добавить tick marks для визуализации значений

- [x] 01.02.26 Кнопки управления гео-объектами (save/edit/delete) отображаются вертикально
  - Должны быть горизонтально в одну строку
  - Поведение нестабильное: иногда горизонтально, иногда вертикально
  - Зависит от ширины popup или количества sub-questions
  - Leaflet Draw popup toolbar CSS fix
