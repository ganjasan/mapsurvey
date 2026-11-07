## 1. Format and views

- [ ] 1.1 `survey/map_styles/io.py`: `FORMAT`, `VERSION`, `export_document(style)`, `parse_document(data) -> (name, base, settings, errors)`, `unique_name(org, name)`
- [ ] 1.2 `survey/map_style_io_views.py`: export (GET, attachment), import (POST multipart); URLs; gates; events
- [ ] 1.3 Library page: Import form in the header, Export link on exportable cards

## 2. Tests, docs, strings

- [ ] 2.1 `survey/tests/test_map_style_import_export.py` for every scenario; `UNMAPPED_MODULES` entry
- [ ] 2.2 Help page section "Export and import a style" with the format; strings in the ten catalogs
- [ ] 2.3 Full suite, `openspec validate --strict`
- [ ] 2.4 Dev check: export Paper A, import into the demo workspace, worker publishes
- [ ] 2.5 PR into `epic/map-styles`, merge, archive in a follow-up PR
