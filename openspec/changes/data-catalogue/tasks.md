## 1. Registry

- [x] 1.0 `layers._object_props`: one builder for the layer feature twins (carried from #666)
- [x] 1.1 `data` app: `apps.py`, `models.Dataset` (D1), migration `0001_initial`, `INSTALLED_APPS`
- [x] 1.2 `data/datasets.py`: `sync(org)` (D2), `visible(org, user)` (D3), row facts and used-by (D4)
- [x] 1.3 `data/features.py`: `question_features(survey, code, scope)` — the reader of an answers dataset

## 2. Catalogue

- [x] 2.1 `data/views.py` `catalogue` + route `/editor/data/` (`editor_data`); sidebar item in `app_nav`
- [x] 2.2 Template `data/catalogue.html` (D5): rows, facet links, search, empty state, links out
- [x] 2.3 New strings in every offered catalog

## 3. Tests and docs

- [x] 3.1 `survey/tests/test_data_catalogue.py`: spec scenarios (existing data appears; removed question leaves; editor without access; counts via scope; filter; sidebar)
- [x] 3.2 `CLAUDE.md`: Data catalogue paragraph; help page `how-to/data.md` + help link
- [x] 3.3 Touched tests + full suite once; `/verify` with a screenshot; `openspec validate --strict`
