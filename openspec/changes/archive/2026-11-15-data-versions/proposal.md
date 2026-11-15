## Why

A council re-inspects its trees every spring. Today that means a new file, a new layer and
re-linking it everywhere — and the answers residents gave about each tree stay on the old layer
(#671, Data epic #676).

## What Changes

- **Upload new version** on a layer dataset's page: the file is read in the background and its rows
  are matched to the dataset's objects by the layer's key field; the page shows how many objects
  will be added, changed, removed and left unchanged — and how many answers hang on the removed
  ones — before anything is saved.
- **Apply** with a change note: matched objects are updated IN PLACE (same row), so answers about
  them (sub-questions, reactions) stay attached; new keys are added, missing keys removed. Every
  survey, Site and report reading the dataset shows the new version at once, because they link it.
- **Version history** on the dataset page: number, date, author, note and counts; an upload made
  from #668 on records version 1.
- Refusals: no key field on the dataset, a file without the key column, more objects than the
  workspace's limit, or more than a survey map takes while the dataset is linked into a survey.

## Capabilities

### New Capabilities
- `data-versions`: new versions of a layer dataset matched by key, previewed before saving, applied
  in place, with a history.

### Modified Capabilities
<!-- none -->

## Impact

- `data/models.py` (`DatasetVersion`; `DataImportJob.target`, `note`, statuses `preview`/`applying`),
  `data/versions.py` (new), `data/tasks.py`, `data/views.py`, `data/templates/data/dataset.html`.
- Help `how-to/data.md`, CLAUDE.md, strings in 10 catalogs.
