## Why

Pressing a geo question's button (point, line, area, spray), editing a placed feature or tapping to place a point hides the question panel on every screen size. On a phone that is right — the panel covers the map. On a computer screen there is plenty of map beside the panel: the respondent loses the question text and their other answers while placing, and with the wider panels of #473 the jump is bigger still. The crosshair and the draw bar are centred on the whole viewport, i.e. partly under a panel that stays (issue #477, epic #478).

This is an OPTION for the creator, not a new default: a section that does not ask for it behaves exactly as today.

## What Changes

- New per-section setting `keep_panel_open` (default off). When on, on a desktop viewport, on a `map` section:
  - starting a placement or drawing (point crosshair, line, area, spray, edit of a placed feature, tap to place) does NOT hide the panel;
  - the crosshair, the point it places, the Cancel/Apply buttons and the draw bar are centred on the VISIBLE map area — the viewport minus the panel, on whichever side it is;
  - moving a placed point re-centres it in the visible area, not under the panel.
- Phones (below 768 px), `image` and `form` sections ignore it. The respondent can still hide the panel by hand; then the whole viewport is the visible area again.
- Fix carried along (bug from #473): the sub-question pop-up's auto-pan padding assumed the panel on the left; with `panel_side = right` a pop-up could open under the panel. The padding now follows the panel's side, setting or no setting.
- Editor: a checkbox in the section modal's Layout block, shown for the Map stage. Safe edit on a live survey; draft copy, duplicate, ZIP, REST and MCP carry it.
- The epic's single "What's new" card is replaced by one with a screenshot of the new layout (owner's request): a new id `2026-10-29-survey-layout-options`, so creators who dismissed the text-only card see it; the old file is removed, keeping one card per epic.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `section-form-layout`: adds the keep-panel-open requirement and the pop-up padding fix; the travel and editor requirements name the new setting.

## Impact

- `survey/models.py` + migration `0108`: `SurveySection.keep_panel_open`; `layout_classes()` adds `panel-keep` on map sections.
- `base_survey_template.html`: one helper decides whether a placement hides the panel (the seven `toggleInfo(false)` call sites), one computes the visible map area (crosshair overlay, `getCrosshairLatLng`, draw bar, re-centring a moved point), the pop-up padding by side; `initSection()` toggles `panel-keep`.
- `partials/survey_section_partial.html` (`data-keep-panel-open`).
- Editor form + modal, ZIP, REST/MCP schemas and descriptions, references, catalogs, help page, the epic's card, CLAUDE.md.
- Tests in `survey/tests/test_section_form_layout.py`, `api/tests/test_v1_structure.py`, `mcp/tests/test_structure.py`.
