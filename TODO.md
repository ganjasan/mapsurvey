# TODO

## Completed

- [x] Survey Import/Export (2026-02-01)
  - CLI: `export_survey`, `import_survey`
  - Web UI: Export dropdown, Import modal
  - Archived: `openspec/changes/archive/2026-02-01-survey-import-export/`

## Editor

- [ ] Implement Delete Survey button in `/editor/`
  - Add `delete_survey` view with confirmation
  - Add URL route `/editor/delete/<name>/`
  - Update template with working link and confirmation modal

## Bugs

- [ ] Slider (range input) отображается без рисок
  - Добавить tick marks для визуализации значений

- [ ] Кнопки управления гео-объектами (save/edit/delete) отображаются вертикально
  - Должны быть горизонтально в одну строку
  - Leaflet Draw popup toolbar CSS fix
