## Why

The Public Results config tab (`/editor/surveys/<uuid>/public-results/`) was built with its own bespoke sidebar CSS (`.pr-*` classes) instead of reusing the WYSIWYG Survey Editor's sidebar classes, even though both share the same 3-column shell (sidebar / center / preview) via `editor_base.html`. Side by side they read as two different products: the block-add control is a permanently-visible select+button pair instead of a dashed "+" affordance, and the "Content blocks" header/list styling drifts slightly from "Sections". Separately, Survey Settings today lives on its own full-page tab, disconnected from the same contextual sidebar pattern Public Results already uses for "Page settings" (pinned entry above the list, center panel swaps contextually).

## What Changes

- **Shared sidebar primitives**: promote the pinned-entry pattern ("Page settings" in Public Results) into `editor_base.html` as shared CSS (`.sidebar-pinned`, `.sidebar-pinned-item`) so both tabs use identical markup/styling instead of parallel near-duplicates.
- **Public Results sidebar**: reuse the Survey Editor's `.editor-sidebar` / `.sidebar-header` / `.section-list` / `.section-item` / `.sidebar-footer` / `.add-question-btn` classes for the blocks list and its header, dropping the bespoke `.pr-sub`/`.pr-blocks`/`.pr-block`/`.pr-add` rules where they'd just duplicate shared ones.
- **Add block as a dashed button + modal**: replace the always-visible block-type/question selects at the bottom of the Public Results sidebar with a single `.add-question-btn`-styled "+ Add block" button that opens a modal (block type + conditional question picker), mirroring "+ New Question" in the Survey Editor. No change to the add-block POST endpoint or its validation.
- **Survey settings pinned into the Editor sidebar**: add a pinned "Survey settings" entry above "Sections" in the Survey Editor sidebar. Clicking it swaps the center panel to a settings form (general fields, default map position, collaborators, password/test access — the same content as today's standalone settings page) via the same HTMX contextual-swap pattern Public Results uses for blocks vs. page settings, with autosave on the general fields.
- **Deprecate the standalone Settings tab**: the top-nav "Settings" tab now links into the Editor tab with the settings panel pre-selected (`?panel=settings`) and is marked with a small "moved" badge. The old standalone URL/view (`/editor/surveys/<uuid>/settings/`) keeps working unchanged (existing links, bookmarks, and tests) — it is not removed, only no longer the primary entry point.

## Capabilities

### Modified Capabilities
- `public-results-page`: editor sidebar now reuses Survey Editor CSS classes; adding a block is a dashed button + modal instead of an always-visible inline form. No change to data, privacy, or rendering behavior.
- `survey-editor`: adds a pinned "Survey settings" sidebar entry with contextual center-panel rendering (mirrors section selection) and autosave on the general settings form; the top-nav Settings tab is marked deprecated and redirects into the new location.

## Impact

- **Templates**: `editor/editor_base.html` (shared pinned-item + deprecated-badge CSS), `editor/public_results.html` (sidebar markup/CSS + add-block modal), `editor/survey_detail.html` (pinned settings entry + JS wiring), `editor/partials/_survey_nav_tabs.html` (Settings tab href/badge), new `editor/partials/survey_settings_panel.html` (extracted from `survey_settings.html` for HTMX-swap use, with autosave), new `editor/partials/pr_add_block_modal.html` and `editor/partials/pr_block_list_item.html` (extracted from `public_results.html`'s inline blocks list).
- **Views**: `survey/editor_views.py` gains `editor_survey_settings_panel` (GET partial / POST autosave, mirrors the pattern in `survey/public_results_editor.py`'s `public_results_save_settings`). `editor_survey_detail` accepts `?panel=settings`. `editor_survey_settings` (old URL) is untouched — no behavior change, no regression risk to existing tests.
- **No data model changes.** No change to the public results page's privacy/aggregation behavior — purely presentational + navigation.
