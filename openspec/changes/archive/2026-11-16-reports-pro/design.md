## Context

Pro features are rows of `billing/features.py`; `billing.entitlements` answers three questions —
`has` (the plan), `covers` (the plan or a live trial, spent or not) and `may` (a new use) — and
`billing.trial` starts a workspace's 90-day trial on its first Pro use. Sites is the closest
precedent: creating and editing are Pro, the public page never checks the plan.

Until this change the public results page was free: every published survey has one, 26 are
published on production (the count per plan is the ship-day task).

## Decisions

1. **`covers`, not `may`, keeps a report alive.** A report made under the trial stays editable and
   live until the trial ends, whatever was counted — "honouring a state set earlier" is exactly
   what `covers` is for. The trial allowance is uncapped (`'reports': None`): the limit of the
   trial is its 90 days, not a number of reports.
2. **A write starts the trial.** `gate.use(org, user)`: covered → yes; never trialled → the write
   starts it (`trial.use`); otherwise no. Every POST of the report editor, the start page, import
   and copy asks it in one place — the `on_survey` / `on_report` wrappers and three views.
3. **Reading never asks.** The editor's GET, export, PDF, ZIP and every public route work on any
   plan: "nothing is deleted", and a customer leaving Pro can still take the report away.
4. **Frozen lazily, at the first request.** `gate.freeze_if_lapsed(report)` runs in the public
   views before rendering: a published live report of an uncovered workspace is frozen as it
   stands. One rule serves the switch (free workspaces that never had the feature) and a lapse,
   needs no scheduler and no migration that would compute entitlements with historical models.
   "As of that moment" is then the first view after the cover ended, not the second it ended; the
   management command freezes all of them at once on ship day so the date is the ship day.
5. **Read-only is the gate plus a banner.** The editor template shows the report, a banner with
   the plan link, and its forms still render; a write answers the upgrade page. Disabling every
   control would be a second gate to keep in step with the first.
6. **The survey's first report is still drafted for free** by `scaffold_report` when the Public
   results tab opens: that is the product drafting, not a member writing, and it is what a free
   workspace sees — read-only — with the reason to upgrade in front of it.
7. **Unfreezing needs the feature**: it is a write like any other.

## Risks / Trade-offs

- [Free workspaces lose editing of a page they have today] → the owner's decision; mitigated by
  the trial starting on the first write (90 days), by the page staying online frozen, and by the
  ship-day letter.
- [A freeze taken on first view after a lapse is later than the lapse] → by at most the time until
  someone opens the page; the command exists for a clean date.
- [Tests of the tab on free workspaces] → moved to Pro workspaces; the suite's helper for a Pro
  workspace already exists.

## Migration Plan

No schema change. On ship day: `freeze_reports_without_pro --dry-run` (the count for the letter),
the letter (owner), then the command without `--dry-run` after the merge. Rollback: revert; frozen
reports stay frozen until their authors press "Back to live data".
