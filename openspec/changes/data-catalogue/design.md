## Context

ADR-001 §4: `data.datasets.Dataset` is a registry row created lazily for existing layers and
questions, backed by existing tables. Owner defaults (2026-11-14): collected answers appear
automatically and aggregated; registry = one table + used-by edges (the edge table comes with the
links of #670); "Data" in the top navigation. Survey access: org owner/admin/viewer see every survey
of the workspace, an org editor only surveys they collaborate on (`permissions`).

## Decisions

**D1 — App and table.** `data` becomes an installed app (`data.apps.DataConfig`), table
`data_dataset`. Fields: `organization` (CASCADE), `kind` (`layer` | `shared_map` | `answers` |
`responses`), `layer` (FK `SurveyMapLayer`, CASCADE, null), `survey` (FK canonical `SurveyHeader`,
CASCADE, null), `question_code`, `name`, `description`, `privacy_class` (`public` | `aggregated` |
`private`), `licence`, `created_at`, `updated_at`. Constraints: one row per layer; one row per
(survey, kind, question_code) for collected kinds; a check that layer kinds carry a layer and
collected kinds a survey. A future upload with no survey (#668) is still a `layer` row.

**D2 — Sync, not signals.** `sync(org)` runs on catalogue load: one query per source kind,
bulk-create the missing rows, delete rows of collected kinds whose question code no longer exists
in the survey's family. Names are refreshed from the source (layer name; question name; survey
name). Signals would have to cover every write path (editor, API, MCP, import, cloning); a sync at
read time cannot miss one, and a workspace holds tens of datasets, not thousands.

**D3 — Who sees what.** Layer and collected rows inherit their survey's access: a member sees a row
when `get_effective_survey_role` gives them any role on the owning survey; org owner/admin/viewer
skip the per-survey check. Counts only — the catalogue never shows a single answer.

**D4 — Row facts.** Rows: `layer` → `feature_count`; `shared_map` → objects of clean sessions;
`answers` → non-trashed answers of that code in the family (moderated included, as Responses
counts); `responses` → non-trashed, non-empty sessions. All through `data.scope`. "Used by": a
layer → its survey plus every question bound to it; `answers` → public results blocks, Site results
blocks and shared-map layers on that code; `responses` → the survey and its results page. Last
change: layer `updated_at`; collected kinds: newest session start.

**D5 — Page.** Extends `base.html` like the Sites list (same container, list-group look); filter
chips are links with query parameters (`?kind=`, `?privacy=`, `?q=`), no JavaScript. A row links to
the survey's map settings (layers) or Responses (collected kinds) until #669's dataset page.

## Risks / Trade-offs

- [Sync cost on every load] → bounded by the workspace's surveys; three aggregate queries; can
  move to a signal-driven refresh later without changing the model.
- [Orphan rows when a survey is trashed] → trashed surveys are excluded from listing; rows go with
  the survey's permanent purge (CASCADE).

## Migration Plan

One new table, created empty; the first catalogue load fills it. Rollback = revert (the table is
derived and can be dropped).
