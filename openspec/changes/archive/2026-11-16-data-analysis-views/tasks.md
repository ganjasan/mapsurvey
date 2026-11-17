## 1. Model and computation

- [x] 1.1 `DatasetView.config`, kinds `engagement | crosstab | coverage | density | responses`, `kind` widened; migration `data/0008`
- [x] 1.2 `data/questions.py` (resolver by code, moved from `reports.sources`); `reports.sources` imports it
- [x] 1.3 `data.aggregate`: `marks` per cell
- [x] 1.4 `data/analysis.py`: `engagement`, `crosstab` (masked cells, withheld margins), `cells` (grid / coverage / density)
- [x] 1.5 `data.dataviews`: `kinds_for`, `clean` with `kind` + `config`, `result(view, lang)`, GeoJSON for the three grid kinds

## 2. Surfaces of Data

- [x] 2.1 `data.services.create_view(kind=, config=)`
- [x] 2.2 dataset page: kind picker, question pickers for a cross-tab, kind label per view, preview page `data/view.html`
- [x] 2.3 REST: `kind` + `config` in `ViewIn`, `GET …/views/{view}/data`; `view_out` carries `config`
- [x] 2.4 MCP: `create_dataset_view` takes the same, new `get_dataset_view_data`
- [x] 2.5 regenerate `reference/api.md` and `reference/mcp-tools.md`

## 3. Saved Responses views

- [x] 3.1 `data/responses_views.py`: table parameters ↔ config (ids ↔ codes), `save`, `params_for(view, service)`
- [x] 3.2 `analytics_views`: save / delete endpoints (editor), `view=<id>` expanded by the table endpoint, `?view=` on the page
- [x] 3.3 Responses table toolbar: Views menu (open, save current filter, delete); dataset page lists them with a link

## 4. Ship

- [x] 4.1 tests: `survey/tests/test_data_analysis_views.py`, `survey/tests/test_responses_saved_views.py`, additions to `test_public_aggregates.py` and `test_data_api.py`
- [x] 4.2 help: `how-to` page section on analysis views; CLAUDE.md
- [x] 4.3 `openspec validate --strict`, touched test modules, full suite, /verify with screenshots, PR into `epic/reports`
