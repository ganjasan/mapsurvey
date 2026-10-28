## Why

The OAuth consent page lists every workspace the grant reaches as one comma-separated line with a
plan chip after each name. A creator with nine workspaces gets a paragraph that pushes *Allow*
down and hides the one thing that matters: which workspaces the assistant can actually work in
(those on Pro). Seen on production while connecting claude.ai, 2026-10-24.

## What Changes

- The workspaces block becomes a folded `<details>`: the summary reads "Workspaces: N · on Pro: M"
  (or the single workspace's name and plan when there is one), and opening it shows a two-column
  table, workspace and plan.
- Rows are ordered with workspaces that have the API (Pro) first, then by name.
- The Free-plan note and everything else on the page stay as they are.

## Capabilities

### New Capabilities

### Modified Capabilities
- `oauth-authorization-server`: how the consent page presents the reachable workspaces.

## Impact

`api/oauth/views.py` (order and counts), `api/templates/api/authorize.html`, `api/tests/`, the ten
offered catalogs for the new strings. No model, no flow change.
