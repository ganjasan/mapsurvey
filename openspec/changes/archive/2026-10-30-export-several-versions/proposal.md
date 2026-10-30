## Why

A paying design-partner studio ran one survey through 11 versions and needs the answers of
versions 10 and 11 only — the final questionnaire. The export offers one version or all of them;
the workaround (export "All versions", then switch the `vN_` layers off in QGIS / Google Earth)
ships every earlier version and mixes them in the flat tables. Issue #496.

## What Changes

- The `version` filter accepts a comma-separated list (`v10,v11`, also `10,11`, `latest,v9`). It
  resolves to exactly those family members, in family order. `all`, a single value, `draft` and a
  missing parameter keep their meaning, so every old link exports what it did.
- A list never mixes the draft copy in (`draft` inside a list is ignored), unresolvable entries are
  dropped, and a list with nothing resolvable falls back to the whole family — the same fallback a
  single bad value has.
- The export dialog shows one check-box per version plus "All versions" as a shortcut, instead of
  the single select. The URL stays copyable and carries `version=v11,v10`. "Draft (test)", where
  offered, stays exclusive. Nothing ticked disables Export.
- Several versions keep the `vN_` file prefixes, as "all" does.
- REST (`GET …/export`, `POST …/export-link`) and MCP (`get_export_link` and the other tools that
  take `version`) accept the same list through the same resolver; only their field descriptions
  and the generated reference pages change.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `version-filter-scope`: a new requirement — a list of versions resolves to those versions; file
  prefixes follow from it.
- `responses-export-formats`: the dialog's version field becomes check-boxes and the URL scenario
  gains the list form.

## Impact

- `survey/versioning.py` (`resolve_version_scope`) — the one parser; export, Responses analytics,
  REST and MCP all read it.
- `survey/templates/editor/partials/_export_modal.html`, `survey/assets/js/export_dialog.js`.
- `api/v1/schemas.py` (`ExportLinkIn.version` description), `mcp/tools/responses.py` (`VERSION`
  description), regenerated `help/…/reference/api.md` and `reference/mcp-tools.md`.
- Tests: `survey/tests/test_version_filter_scope.py`, `survey/tests/test_responses_export_formats.py`.
- No migration, no new dependency.
