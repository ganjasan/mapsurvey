## 1. Data

- [x] 1.1 `LandingFile` model + `documents`, `map` kinds; migration

## 2. Domain

- [x] 2.1 `landings.py`: kinds in `BLOCK_KINDS`, `_clean_documents`, `_clean_map`, `check_document(upload)`, `parse_geojson(upload)`, `file_type_label`
- [x] 2.2 `content_screening.collect_landing_text`: document titles

## 3. Builder and page

- [x] 3.1 `landing_views._save_block`: map upload + options; documents add / rename / remove; the base-map choices in the form context
- [x] 3.2 Form fields in `_block_form.html`; `landings/blocks/documents.html`, `landings/blocks/map.html`; Leaflet + map script on `public.html` only with a map block; CSS

## 4. Tests, docs, strings

- [x] 4.1 Tests for every new scenario in `test_survey_landings.py`
- [x] 4.2 Help page sections; translations
- [x] 4.3 Full suite, `openspec validate --strict`, dev check with screenshots
- [ ] 4.4 PR into `epic/landing-pages`, merge
