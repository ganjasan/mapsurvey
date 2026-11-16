## Context

`PublicResultsPage` is `OneToOne` with `SurveyHeader`; `PublicResultsBlock.question` is a FK to a
question row. `publish_draft()` replaces question rows, so the renderer already resolves a block's
answers by "same code + input type within the version family" and ignores which row the FK names.
Data v1 (#676) gives every survey a `responses` dataset and every top-level geo question an
`answers` dataset, keyed by the canonical survey and the question code.

## Goals / Non-Goals

**Goals:** one report model in its own app; existing pages intact at their addresses; blocks
anchored by dataset + code; multi-survey reports possible; used-by for reports.

**Non-Goals:** a new editor, new block types, analysis view types, a Pro gate, API. No change to
what a public page shows.

## Decisions

1. **Copy, then drop — not a table rename.** `reports/0001` creates the tables in their final
   shape, `reports/0002` copies every page and block **with its primary key**, `survey/0131`
   repoints `CommentThread.block` and deletes the old models. 176 pages and 966 blocks: a copy is
   one function that a migration test can run; a cross-app rename through
   `SeparateDatabaseAndState` plus four follow-up schema steps is harder to review. Ids are kept so
   comment anchors, frozen snapshots (`blocks[].id`) and `?block=<id>` links survive.
2. **A block names a dataset and a question code.** Map blocks → the `answers` dataset of
   (canonical survey, code); chart, objects and budget blocks → the survey's `responses` dataset
   plus the code. `ReportBlock.question` is a cached property that resolves the current question
   of that code in the dataset's survey family (canonical first). This is the anchoring rule
   comments and translations already use, and it is what lets one report read two surveys.
   Alternative considered: a `DatasetView` per block created by the migration — it would put some
   900 generated views on customers' Data pages for no visible gain; a block may carry an optional
   `view` (a grid view of an answers dataset) and #692 adds the view types charts need.
3. **Missing dataset rows are created on the way.** Registry rows are written by a read-time
   `data.datasets.sync(org)`; the migration and `reports.sources.dataset_for()` create the row a
   block needs with the same values `sync` would write.
4. **`dataset` is `SET_NULL`, `view` is `RESTRICT`.** `sync` drops a collected dataset when its
   question disappears; the block then renders nothing, exactly as a deleted question did
   (`SET_NULL` on the old FK). A view in use by a block refuses deletion like a view linked into a
   survey.
5. **A report keeps a home survey (`Report.survey`, nullable FK, no longer unique).** The survey's
   Public results tab, the thanks-page button, the Share page and the dashboard pill read
   `SurveyHeader.report` — the survey's oldest report, which for every migrated survey is its old
   page. A report without a survey and several reports per survey are valid rows; the UI to create
   them comes with #704/#705.
6. **The editor screens stay, over the new model.** Views move to `reports/editor_views.py` with
   the same URL names under `/editor/surveys/<uuid>/public-results/`. Replacing them is #704; doing
   both here would leave no reviewable migration.
7. **Workspace-only visibility** is a third value of `visibility`; `/r/<slug>/` answers 404 to a
   non-member and sends an anonymous visitor to login. Always `noindex`, never in the sitemap or
   the stories listing.
8. **Function names follow the object** (`scaffold_report`, `freeze_report`, `ReportService`); the
   templates keep their file names until #704 replaces them.

## Risks / Trade-offs

- A page attached to a draft copy or an archived version (the config tab creates one for whatever
  header is open) → blocks resolve the dataset through `canonical_of`, the report keeps its
  `survey` FK as it was.
- A block whose question row is gone (`question_id IS NULL` on a chart/map block) → copied with no
  dataset; it rendered nothing before and renders nothing after.
- Explicit primary keys leave the identity sequences behind → the copy resets both sequences.
- Preview and local databases with no pages → the copy is a no-op.

## Migration Plan

Deploys with the epic branch. Reverse of `0002` is a no-op (the old tables are dropped by `0131`,
whose reverse recreates them empty); rollback is a database restore, as for any destructive
migration — rehearse on a production copy before the final PR.
