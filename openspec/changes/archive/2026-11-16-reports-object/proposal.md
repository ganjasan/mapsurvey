## Why

The public results page is one page per survey with its own model, bound to question rows. The
Reports module (Vision `requirements/vision/reports.md` in the ops repo, epic #712, issue #703)
needs a workspace object that references datasets of the Data module and owns no data — and there
must never be two systems side by side, so the existing pages move first.

## What Changes

- New app `reports`: `Report` (a workspace object with a public address `/r/<slug>/`, live or
  frozen, a visibility, a K threshold) and `ReportBlock` (an ordered block that names a **dataset**
  of the Data module and, for a block about one question, that question's **code** — never a
  question row).
- Every `PublicResultsPage` / `PublicResultsBlock` becomes a report and its blocks with the same
  ids, slug, blocks, visibility, live/frozen state, snapshot and K. **BREAKING (internal):** the two
  old models are removed; `survey.public_results` becomes `reports.render`.
- A report's blocks may read datasets of several surveys of the workspace.
- A third visibility, **workspace only**: a published report that only signed-in members of the
  workspace can open.
- A **Reports** list in the editor navigation; a survey's Public results tab opens that survey's
  report as before.
- "Used by": a dataset's page, delete page and the catalogue name the reports that read it; a view
  a report block shows cannot be deleted.
- Writes go through `reports.services` with an `Actor`.

Out of this change: the story editor and the new block set (#704), analysis views (#692), the
start cards (#705), PDF/embed (#707, #708), the Pro gate (#709), API and MCP (#710). The editor
keeps today's configuration screens over the new model until #704 replaces them.

## Capabilities

### New Capabilities
- `reports`: the report object, its blocks over Data datasets, the Reports list, workspace-only
  visibility, migration of the existing pages.

### Modified Capabilities
- `public-results-page`: the page is a report; it is no longer bound 1:1 to a survey.
- `data-links`: the places that use a dataset include reports.

## Impact

- New `reports/` (models, migrations, `render.py`, `services.py`, `sources.py`, `editor_views.py`,
  `views.py`, `urls.py`, templates); `survey/public_results.py` and
  `survey/public_results_editor.py` move there; `survey/models.py` loses two models
  (migration `0131`), `CommentThread.block` points at `reports.ReportBlock`.
- `survey/views.py` (`/r/<slug>/`, sitemap, dashboard), `survey/sites.py`, `share.py`,
  `share_views.py`, `comments.py`, `basemaps.py`, `admin.py`, `services/`, two management commands,
  templates that read `survey.public_results_page`.
- `data/datasets.py`, `data/links.py`, `data/dataviews.py`, `data/services.py`.
- CLAUDE.md; tests that build pages and blocks.
