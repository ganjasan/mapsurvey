## Why

Data v1 (#676) shipped views as saved filters: an objects view of a layer and a grid-of-counts view
of collected answers. The Reports module (epic #712) needs views that *compute* something — who
took part, how two questions relate, where shapes overlap, where marks pile up — and it must not
compute them itself: the Vision's BO-4 is "no aggregation, masking or density code inside the
module". The Responses page has filters a creator rebuilds by hand every visit, and a report cannot
point at "women over 60" because that filter is nowhere but the browser's memory.

Issue #692, second item of epic #712 (after #703, before the block set #704).

## What Changes

- **Four analysis view kinds** next to `objects` and `grid`, all computed in `data` through
  `data.scope.SessionScope.public` and `data.aggregate`:
  - `engagement` (a `responses` dataset): opened → answered → finished, and the same three per day,
    week or month;
  - `crosstab` (a `responses` dataset): two choice-type questions, a table of distinct respondents;
  - `coverage` (an `answers` dataset of a line or area question): per grid cell, the respondents
    whose shape reaches it and their share of everyone who drew;
  - `density` (an `answers` dataset of a point or spray question): per grid cell, the marks in it.
- **Privacy bound in one place**: every count under K is masked (`data.aggregate.mask`), a cell
  under K is omitted (`data.aggregate.grid`), a table margin that would give a masked cell away is
  withheld. A view kind is offered only on the dataset kinds above; there is no unmasked reading of
  a view on any surface, the API and MCP included.
- **Saved Responses views**: the Responses page saves its current filter under a name as a
  `DatasetView` of kind `responses` over the survey's `responses` dataset, keyed by question and
  choice CODES (rows are replaced on publish), lists the saved views and re-applies one. The dataset
  page lists them with a link back to Responses.
- `DatasetView.config` (JSON) holds what a kind needs (the two question codes, the filter state);
  `DatasetView.kind` widens to fit the new names.
- `data.aggregate.grid` also reports `marks` per cell (points and spray dots inside it).
- The dataset page creates and previews analysis views; REST gets `kind` + `config` on view
  creation and `GET /datasets/{id}/views/{view}/data`; MCP `create_dataset_view` takes the same and
  `get_dataset_view_data` reads a result.
- The question resolver by code (`reports.sources._questions_of`) moves to `data` — Reports reads
  Data, never the reverse.

## Capabilities

### New Capabilities
- `data-analysis-views`: the four computed view kinds, their privacy bound and their outputs.
- `responses-saved-views`: saving, listing, opening and deleting a Responses filter as a view.

### Modified Capabilities
- `public-aggregates`: the grid reports marks per cell.
- `data-api`: view creation takes `kind` and `config`; a view's computed result is readable.

## Impact

- `data/models.py` (+ migration `data/0008`), `data/dataviews.py`, new `data/analysis.py`,
  `data/questions.py`, `data/aggregate.py`, `data/services.py`, `data/views.py`,
  `data/templates/data/dataset.html`, new `data/templates/data/view.html`.
- `survey/analytics_views.py`, `survey/urls.py`, `editor/analytics_dashboard_v2.html`,
  `css/responses-v2.css` — the saved-views menu.
- `api/v1/datasets.py`, `mcp/tools/data.py`, generated `help/.../reference/api.md` and
  `mcp-tools.md`.
- `reports/sources.py` imports the resolver from `data`.
- No reader yet: report blocks that show these views are #704. No production data changes; the
  migration adds one column and widens one.
