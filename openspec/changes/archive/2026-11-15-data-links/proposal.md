## Why

A layer belongs to one survey: the same tree register has to be uploaded again for the next
survey and again for the Site, and nobody can see which surveys or sites show a dataset before
changing or deleting it (#670, Data epic #676).

## What Changes

- **"From Data"** on a survey's Reference layers card: pick a public layer dataset of the workspace
  and it is LINKED, not copied — the survey's maps, Responses, print and export read the
  dataset's own objects, so an edit of the dataset shows everywhere. Per link, the creator picks
  which fields the respondent's object card shows. Unlink from the same card.
- **Site map block** can show a dataset instead of an uploaded area file; the page fetches the
  dataset's GeoJSON from a gated endpoint (never inlined).
- **Used by**: every link is a `DatasetLink` row (survey or site block). The dataset page lists
  every place that uses it — the owning survey, linked surveys, site blocks, the questions bound
  to it — and so does the delete page of a workspace dataset before the delete is confirmed.
- **Guards**: only a `public` dataset can be linked into a survey or a site; a linked dataset
  cannot be made private; a dataset above the survey layer caps (5,000 objects / 10 MB) cannot be
  linked into a survey (memory rules); a link counts toward the 10 layers per survey; a link (or
  dataset) a question of the survey is bound to cannot be removed.

## Capabilities

### New Capabilities
- `data-links`: datasets linked into surveys and Site map blocks, used-by records, deleting a used
  dataset.

### Modified Capabilities
<!-- none -->

## Impact

- `data/models.py` (`DatasetLink`, migration), `data/links.py` (new), `data/views.py`,
  `data/templates/data/dataset.html`, `data/templates/data/delete.html`.
- `survey/layers.py::layers_for` (owned ∪ linked public layers), `survey/views.py::_gated_layer`
  and the object card, `survey/editor_views.py` + the settings card, `survey/sites.py` /
  `survey/services/sites.py` / site templates and JS, `survey/site_views.py` (dataset endpoint).
- Help pages `how-to/data.md`, `how-to/sites.md`; CLAUDE.md; strings in 10 catalogs.
