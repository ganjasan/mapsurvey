## Why

A workspace's place data has no home: a reference layer belongs to the survey it was uploaded
into, answers to the survey that collected them, and nobody can list what the workspace holds.
Data is the first platform module (Vision v0.4, Data Vision v0.2); its catalogue is what every
later item builds on — uploads (#668), metadata (#669), "From Data" links (#670), versions (#671),
views (#672), tags (#673), API/MCP (#674). Issue #667, epic #676.

## What Changes

- New Django app `data` with one model, `Dataset`: a registry row over existing data —
  `layer` (an uploaded or drawn reference layer), `shared_map` (a layer materialised from answers),
  `answers` (a survey's answers to one geo question, by code across versions), `responses` (a
  survey's respondent rows). Privacy class per row (`public`, `aggregated`, `private`); collected
  kinds default to `aggregated`, creator layers to `public` (respondents already see them). No data
  moves; the registry references layers by FK and surveys by their canonical row.
- `data.datasets.sync(org)`: idempotent — creates the rows a workspace is missing and drops rows
  whose source is gone. Runs when the catalogue opens.
- `data.features.question_features(...)`: the one reader of a collected `answers` dataset as
  features (first user: the catalogue's row counts; later the dataset page and API).
- The catalogue at `/editor/data/`: a **Data** item in the app sidebar; one row per dataset the
  member may see (surveys follow survey roles), with source, rows, privacy, "used by" and last
  change; facets for source and privacy; search by name. Rows link to where the data lives today
  (the survey's layer settings or Responses) until the dataset page arrives in #669.
- Refactor carried from #666: layer object features are built by one `_object_props` helper.

## Capabilities

### New Capabilities
- `data-catalogue`: the dataset registry, what appears in it, who sees what, and the catalogue page.

### Modified Capabilities
<!-- none: existing surfaces keep their behaviour -->

## Impact

- New app `data` (models, migration `data/0001_initial`, `INSTALLED_APPS`), `data/datasets.py`,
  `data/features.py`, `data/views.py`, `survey/urls.py` (route), `survey/app_nav.py` (sidebar
  item), template `data/catalogue.html`; new strings in every offered catalog.
- No change to surveys, layers, answers, exports or public pages.
- Tests: `survey/tests/test_data_catalogue.py`.
