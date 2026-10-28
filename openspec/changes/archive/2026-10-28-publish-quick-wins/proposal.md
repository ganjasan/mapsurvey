## Why

The Publish-space UX audit (`docs/ux-review-2026-07/publish-ux-audit.md`) produced a wave of low-risk, high-polish findings that should land before the Publish release: a workflow dead-end after adding a block (P3), an inconsistent published/live vocabulary (P4), unclickable switch labels (P6), machine-token visualization names (P8), a privacy note shown even when masking is off (P9), and "Slug" jargon (P12). All are template/copy-level; none touch the data model or privacy behavior.

## What Changes

- **P3**: after adding a block, redirect to that block's config (`?block=<id>`) instead of Page settings.
- **P4**: one term — **Live**: the page-settings toggle becomes "Page is live"; the publishing widget distinguishes "Draft — not live yet" (page exists, unpublished) from "Set up a results page…" (no page); editor `<title>`s say "Publish – …" (and "Results – …" for analytics).
- **P6**: settings/block switch rows become `<label>`-wrapped so their text toggles the checkbox.
- **P8**: visualization selects show human labels ("Bar chart", "Heatmap", "Markers"…) over the same stored values.
- **P9**: the "Small groups are masked…" note renders only when `k_anonymity_threshold > 1`.
- **P12**: "Slug" is labeled "Page address" (field name and Apply mechanics unchanged).

## Capabilities

### Modified Capabilities
- `public-results-page`: editor polish only — block-add lands in the new block's config; Live vocabulary; labeled switches; human viz names; conditional k-anonymity note; "Page address" label. No changes to data, endpoints' contracts, or privacy.

## Impact

- `survey/public_results_editor.py` (redirect target; viz options become (value, label) pairs), `survey/templates/editor/public_results.html`, `survey/templates/editor/partials/_publishing_widget.html`, `survey/templates/public_results.html`, `survey/templates/editor/analytics_dashboard.html` (title only).
- Tests: 2 added (block-add redirect; conditional k-anon note). No migrations.
