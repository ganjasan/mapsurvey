## 1. Shared sidebar CSS in `editor_base.html`

- [x] 1.1 Add `.sidebar-pinned` / `.sidebar-pinned-item` / `.sidebar-pinned-item.active` / `.sidebar-pinned-item .chev` (moved from `public_results.html`'s bespoke `.pr-pinned`/`.pr-page-item`)
- [x] 1.2 Add `.badge-moved` (muted gray, same shape as `.badge-beta`) for the deprecated nav tab indicator

## 2. Public Results sidebar restyle

- [x] 2.1 Sidebar container reuses `.editor-sidebar`; drop bespoke `.pr-sidebar` width/border rules
- [x] 2.2 "Page settings" pinned entry reuses `.sidebar-pinned`/`.sidebar-pinned-item` instead of `.pr-pinned`/`.pr-page-item`
- [x] 2.3 "Content blocks" header reuses `.sidebar-header`; drop `.pr-sub`
- [x] 2.4 Block list reuses `.section-list`; each `<li>` gets `class="section-item pr-block"` (keep `pr-block` only for the type icon + hidden-eye indicator); drop the now-redundant `.pr-blocks`/`.pr-block` hover/active/padding rules
- [x] 2.5 Extract each block `<li>` into `editor/partials/pr_block_list_item.html`
- [x] 2.6 Replace the always-visible block_type/question_id selects with a `.add-question-btn`-styled "+ Add block" button inside `.sidebar-footer`, opening a Bootstrap modal
- [x] 2.7 Extract the add-block form into `editor/partials/pr_add_block_modal.html` (block_type select, conditional question_id select, unpublishable-question note) — same form fields, same POST target (`editor_public_results_block_add`), no server-side changes
- [x] 2.8 Verify SortableJS reorder and delete-on-hover still work against the new markup

## 3. Editor: pinned "Survey settings" sidebar entry

- [x] 3.1 New URL `editor/surveys/<uuid>/settings-panel/` → `editor_survey_settings_panel` in `survey/urls.py`
- [x] 3.2 New view `editor_survey_settings_panel` in `survey/editor_views.py`: GET renders `editor/partials/survey_settings_panel.html`; POST saves `SurveyHeaderForm` fields and returns JSON for XHR (mirrors `_is_ajax` branch in `public_results_save_settings`) or redirects for plain submits
- [x] 3.3 Extract `editor/partials/survey_settings_panel.html` from `survey_settings.html`'s body (General form + Default Map Position + Collaborators + Password/Test Access), converting the General form to `data-autosave` with the same JS pattern as `public_results.html` (debounced text, immediate selects/checkboxes, status indicator, slug-less — no slug field here so no exclusion needed)
- [x] 3.4 `editor_survey_detail` view: accept `?panel=settings`; when present, context signals the initial center panel should load the settings panel instead of `current_section`, and no section is marked current
- [x] 3.5 `survey_detail.html`: add the pinned "Survey settings" entry above the sidebar header, using `.sidebar-pinned`/`.sidebar-pinned-item`; wire initial `hx-get`/`hx-trigger=load` to the settings-panel URL when `?panel=settings` was passed
- [x] 3.6 `survey_detail.html` JS: click handler for the pinned entry (HTMX GET into `#section-content`, clear all `.section-item.active`, set pinned entry active); extend the existing section-click handler to clear the pinned entry's active class
- [x] 3.7 Reuse the autosave JS helper (debounce/status/postForm) — factor it out of `public_results.html`'s inline script into a small shared script file if duplicating it verbatim starts to hurt; otherwise duplicate minimally, consistent with existing per-template inline-script conventions

## 4. Deprecate the standalone Settings tab (non-destructive)

- [x] 4.1 `_survey_nav_tabs.html`: change the "Settings" tab href to `{% url 'editor_survey_detail' survey.uuid %}?panel=settings`, add a small `.badge-moved` "moved" indicator
- [x] 4.2 Leave `editor_survey_settings` view/URL/template exactly as-is — no behavior change, no test updates expected

## 5. Tests

- [x] 5.1 Settings panel: GET returns the panel partial; POST via XHR returns JSON and persists fields; POST without XHR redirects
- [x] 5.2 `editor_survey_detail?panel=settings` renders with the settings panel as initial content and no section marked current
- [x] 5.3 Add-block modal: submitting the modal form still creates the block and still 400s on a non-publishable (text) question — endpoint unchanged, so this mostly re-confirms existing coverage still passes against new markup
- [x] 5.4 Full `./run_tests.sh survey` run — confirm zero regressions in the ~10 existing tests that hit `/editor/surveys/<uuid>/settings/` directly

## 6. Manual verification

- [x] 6.1 Side-by-side: Survey Editor sidebar vs. Public Results sidebar look visually consistent (header, list rows, footer button)
- [x] 6.2 Clicking "Survey settings" in the Editor sidebar swaps the center panel without a full reload; clicking a section afterward swaps back and clears the pinned entry's active state
- [x] 6.3 Old `/editor/surveys/<uuid>/settings/` still renders correctly when visited directly
- [x] 6.4 Add-block modal in Public Results: add a chart/map/text block, confirm it appears in the list and the live preview updates

## 7. Follow-up refinements to the Add Block modal

- [x] 7.1 Retire the `counter` block type (duplicated the page-level `show_response_count` hero affordance): removed from `PUBLIC_RESULTS_BLOCK_TYPE_CHOICES`, `_build_block`, the add-block endpoint, and both icon templates; folded into migration `0032` (unreleased branch, so no separate correction migration) and deleted the one dev-only counter row
- [x] 7.2 Rename the "Question…" option to "Question results…" for clarity
- [x] 7.3 Show each question's type and current response count directly in the question picker's option labels (`_survey_questions()` now returns `input_type_display`/`answer_count`, rendered inline as "Name — Type · N responses")
- [x] 7.4 Add an `image` block type: one creator-uploaded image + optional multilingual caption (reuses `content` like text blocks); `PublicResultsBlock.image` (ImageField); add/edit endpoints accept `request.FILES`; public template renders `<img>` + `<figcaption>`; a block with no file attached is defensively omitted from rendering
- [x] 7.5 Tests: counter rejected (400), image add/edit/reject-without-file, image payload building (with/without file), image renders on the public page; full suite green (673 tests)
- [x] 7.6 Replace the native question `<select>` with a custom listbox (`.pr-custom-select`) so long question labels wrap onto multiple lines instead of overflowing the modal — a native `<select>` popup cannot wrap option text in any browser. The original `<select>` stays hidden and is still what gets submitted (disabled options, value, and `name="question_id"` unchanged); the custom listbox is built from its `<option>`s via JS and keeps them in sync (click → `select.selectedIndex` + `change` event)
- [x] 7.7 Custom listbox polish: a persistent chevron affordance (name in an ellipsized `flex:1` span so the chevron is never pushed off), the question's type/count moved to its own muted second line (`.pr-opt-meta`), and a sticky search box at the top of the dropdown filtering by name AND type (case-insensitive substring over `qname + meta`), with a "No matching questions." empty state
- [x] 7.8 Selecting a block scrolls the live-preview iframe to that block and flashes it: `data-block-id` anchors already exist on the public template; the editor reaches into the same-origin iframe on every load and calls `scrollIntoView` + a one-shot `.pr-preview-highlight` CSS flash (public blocks got `scroll-margin-top` so they land below the sticky top)
- [x] 7.9 Fix the `heatmap` map viz (it rendered markers on top of the heat canvas, hiding it): in heatmap mode the public renderer now filters out point markers via `L.geoJSON({filter})` and draws only `L.heatLayer` (bounds still fit from the raw point coords). Root cause was markerPane (z-index 600) covering the heat canvas in overlayPane (400)
- [x] 7.10 Per-block map basemap selection: new `PublicResultsBlock.basemap` field (`streets`/`satellite`/`topo`, default `streets`; migration `0035`), a Basemap select in the map-block config (autosaves), server-side validation against `BASEMAP_CHOICES`, and self-contained tile providers on the public page (OSM / Esri World Imagery / OpenTopoMap — no Mapbox token needed). Tests: payload carries basemap, defaults to streets, endpoint saves valid + ignores invalid
