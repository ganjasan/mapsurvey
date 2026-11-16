## Why

"Only trees in poor condition" or "only one question's answers, as counts" is set up again on every
surface that needs it, and Site blocks and (later) reports need something stable to point at
(#672, Data epic #676).

## What Changes

- A **view** is a saved, named filter, field set and colour over a dataset, with a stable id. It is
  created on the dataset's page and is listed there with what uses it.
- A view of a **layer** dataset shows the objects that match its conditions (field
  equals / is one of / greater / less), with only its fields; it is picked in the survey's
  "From Data" picker and in a Site map block exactly like a dataset, still linked, not copied.
- A view of an **answers** dataset (privacy `aggregated`) can only be a grid of counts: cells
  counting distinct respondents, cells under K omitted, through `data.aggregate`. It can be shown in
  a Site map block, never in a survey's layers, and no endpoint returns its marks.
- Conditions and fields name public fields only; a view in use cannot be deleted.

Out of this change (follow-up issue): analysis view types beyond the grid (engagement, cross-tab,
coverage) and moving Responses' saved views onto views — they need the Reports module's reader.

## Capabilities

### New Capabilities
- `data-views`: saved views over datasets, picked by surveys and Site map blocks, bounded by the
  dataset's privacy class.

### Modified Capabilities
<!-- none -->

## Impact

- `data/models.py` (`DatasetView`, `DatasetLink.view`), `data/dataviews.py` (new), `data/links.py`,
  `data/views.py`, `data/templates/data/dataset.html`; `survey/layers.py` (map metadata),
  `survey/views.py` (layer GeoJSON and object card), `survey/editor_views.py` + the layer card,
  `survey/sites.py`, `survey/site_views.py`, the Site block form.
- Help `how-to/data.md`, CLAUDE.md, strings in 10 catalogs.
