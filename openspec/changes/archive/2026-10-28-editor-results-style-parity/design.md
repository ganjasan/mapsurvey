## Context

Both the Survey Editor (`survey_detail.html`) and the Public Results config tab (`public_results.html`) extend `editor_base.html` and share its 3-column shell (sidebar / center / preview), but Public Results grew its own `.pr-*` CSS instead of reusing the Editor's sidebar classes. The user wants the two to read as one product, and specifically wants block/section creation and a settings entry point to look and behave alike.

## Goals

- One shared CSS vocabulary for "pinned sidebar entry above a list" and "list of things with hover/active/delete", used by both tabs.
- Adding a block feels like adding a question: a dashed button that opens a small modal, not a permanently-visible form.
- Survey settings reachable from inside the Editor's sidebar with the same contextual-swap UX as Public Results' "Page settings ↔ block config" split.
- Zero regression risk to the ~30 existing tests that hit `/editor/surveys/<uuid>/settings/` directly.

## Non-Goals

- No change to `PublicResultsPage`/`PublicResultsBlock` data model or the add-block validation rules (text questions still rejected server-side).
- No removal of the standalone `/editor/surveys/<uuid>/settings/` URL or view — it stays fully functional, just de-emphasized in navigation.
- No attempt to make the right-hand preview pane aware of "Survey settings" (it keeps showing whatever section was last previewed; settings has no single preview target).

## Decisions

### Decision 1: Promote pinned-item CSS into `editor_base.html`, not a copy in each template
`.sidebar-pinned` / `.sidebar-pinned-item` (padding, border-bottom, `.active` accent state, chevron) move from `public_results.html`'s inline `<style>` block into the shared base stylesheet. Both "Page settings" (Public Results) and the new "Survey settings" (Editor) use the identical classes. This guarantees pixel parity going forward instead of two hand-tuned near-duplicates drifting apart again.

**Why not keep `.pr-*` and add matching `.sidebar-*` rules separately?** Because the whole point of the request is "these should look the same" — defining the rule once and consuming it twice is the only way that stays true after the next edit.

### Decision 2: Blocks list reuses `.section-list` / `.section-item`, not a redesigned `.pr-block`
The two rule sets were already near-identical (list-style, padding, border-bottom, hover/active background, drag-handle color). Rather than tune `.pr-block` to match, the block `<li>` gets `class="section-item pr-block"` — `section-item` for the shared shell (padding/hover/active/drag-handle/delete-opacity-on-hover), `pr-block` retained only for the block-specific type icon and the "hidden" eye indicator that sections don't have. This also fixes a small existing inconsistency: the delete button on a Public Results block was always visible; sections reveal it on hover only. Reusing `.section-item` naturally picks up that convention.

### Decision 3: Add-block becomes a static modal, not an HTMX-loaded one
The Survey Editor's "+ New Question" modal is HTMX-loaded per click because the form depends on instance state (editing vs. creating, existing choices). The Public Results add-block form has no such per-instance state — same three options every time. So the modal body is rendered statically once per page load (like the modal shell already is), and the existing `editor_public_results_block_add` endpoint is unchanged: same POST target, same redirect-on-success/400-on-invalid-question behavior. Only the trigger button and surrounding chrome move from "always visible inline row" to "dashed button → modal". This keeps the server-side diff to zero for this piece.

### Decision 4: Settings panel is a new parallel view, the old URL is untouched
`editor_survey_settings_panel` is a new view/URL (`/editor/surveys/<uuid>/settings-panel/`) that renders a partial (`survey_settings_panel.html`, extracted from the body of `survey_settings.html`) for HTMX swap into `#section-content`, with the general-fields form converted to autosave (mirroring `public_results_save_settings`'s `_is_ajax` JSON-vs-redirect branch). `editor_survey_settings` (the full-page view) is **not** modified — its GET/POST behavior, template, and URL stay exactly as they are today, so the ~30 tests exercising `/editor/surveys/<uuid>/settings/` directly keep passing unchanged. Only `_survey_nav_tabs.html`'s "Settings" link changes where it points (`editor_survey_detail?panel=settings` instead of `editor_survey_settings`), plus a small "moved" badge — the old page remains reachable for anyone with a bookmark or direct link.

**Why not migrate the old view/tests instead of adding a parallel one?** The old page has ~10 tests spanning ownership checks, basemap serialization, and published-survey editability. Rewriting those to hit a new URL is churn unrelated to the actual ask (visual/navigational parity) and adds regression risk for no user-visible benefit — the old URL isn't gone, it's just no longer the linked-to path.

### Decision 5: `?panel=settings` query param, not a URL segment or hash
`editor_survey_detail` already uses `?section=<id>` for server-side initial-section selection on full page load. `?panel=settings` follows the same convention: on full load with `?panel=settings`, the server renders the settings panel as the initial `#section-content` (via its own `hx-get` on the wrapping div, same mechanism `current_section` already uses) and marks the pinned item `active` server-side; no section gets `active`. Client-side switching (clicking the pinned item after the page is loaded) is a plain HTMX GET + manual `active`-class toggling, exactly like clicking a section today — no `pushState`/hash changes, consistent with the fact that section clicks don't change the URL either.

## Risks / Trade-offs

- Two ways to reach the same settings form (pinned panel vs. standalone page) is mild duplication; accepted because rewriting the standalone page's tests is out of scope and the standalone page remains a reasonable fallback (e.g. for owners who deep-link to it).
- The settings panel partial re-renders Leaflet map init JS on every HTMX swap into `#section-content` (same as section switching does today for section map pickers) — acceptable, matches existing behavior, no new pattern introduced.

## Migration Plan

Purely additive/CSS + one new view+URL+template. No data migration. Existing survey settings page/tests untouched.
