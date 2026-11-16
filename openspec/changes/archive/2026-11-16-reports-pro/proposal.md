## Why

Owner decision of 2026-11-16: Reports is a Pro module as a whole and fully replaces the public
results page; a published page of a free workspace becomes a frozen snapshot at the switch —
readers keep the link, the author edits again on Pro — and the same rule serves a lapsed
subscription: read-only, never a 404. Issue #709 (epic #712).

## What Changes

- **Feature `reports`** in the billing registry, in the Pro trial without a cap (counted).
- **Writes are gated, reading is not** (`reports/gate.py`): creating a report, changing a block or
  a setting, publishing, importing and copying need the feature — by plan, by a live trial, or by
  starting the workspace's trial with that write. Without it the editor opens read-only with the
  upgrade path and every write answers the upgrade page. Export, PDF and the public page never ask
  for the plan. **BREAKING** for free workspaces: the Public results tab is no longer editable
  once their trial is over.
- **A published live report of a workspace without the feature is frozen** the first time it is
  asked for (`gate.freeze_if_lapsed`): the page keeps opening at the same address with the numbers
  of that moment and its "Data as of" date. Nothing is deleted; unpublished reports keep their
  configuration.
- **`manage.py freeze_reports_without_pro [--dry-run]`** lists, and freezes, those reports — the
  ship-day count of affected pages and the "at the switch" step.
- Event `report_paywall_shown` (surface), so purchases after it can be counted.

## Capabilities

### New Capabilities
- `reports-pro`: the gate on writes, the read-only editor, the frozen snapshot of a workspace
  without the feature, the management command.

### Modified Capabilities

None.

## Impact

- `billing/features.py` (feature + trial allowance), `billing/trial.py` (labels); new
  `reports/gate.py`, `survey/management/commands/freeze_reports_without_pro.py`;
  `reports/editor_views.py`, `reports/views.py`, `reports/render.py` (no auto-scaffold write for an
  ungated workspace is still allowed: drafting the first report is not a write by a member),
  `editor/public_results.html`, `reports/list.html`, `reports/start.html`.
- Tests of the Public results tab that used a free workspace move to a Pro one where they test
  editing; tests of the public page keep free workspaces only where freezing is the point.
- Ops, not code: counting the published pages of free workspaces on production and writing to
  their owners with the date — prepared for the owner, sent by the owner.
