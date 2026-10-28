## 1. Model

- [x] 1.1 `SurveySection.keep_panel_open` (BooleanField, default False); `layout_classes()` adds `panel-keep` for map sections
- [x] 1.2 Migration `0108_section_keep_panel_open`

## 2. Respondent page

- [x] 2.1 `survey_section_partial.html`: `data-keep-panel-open`; `initSection()` toggles `panel-keep` (map sections only)
- [x] 2.2 `keepPanelWhilePlacing()`, `hidePanelForPlacement()` replacing the seven `toggleInfo(false)` calls
- [x] 2.3 `visibleMapArea()`; crosshair overlay + actions, `getCrosshairLatLng()`, draw bar and the marker-move pan follow it; inline styles cleared on hide
- [x] 2.4 `_subquestionPopupOptions()` pads by the panel's side (bug from #473)
- [x] 2.5 Manual pass (panel right/half, setting on): point — panel stays, crosshair at the visible centre, the stored point exactly under the tip (464, 513), pop-up beside the point; line — panel stays, draw bar at the visible centre; setting off — panel hides, crosshair at the viewport centre; 390 px — setting ignored. NOT checked by hand: spray, moving a placed point, the hand-hidden panel, a pop-up near the right-hand panel edge

## 3. Editor

- [x] 3.1 `SurveySectionForm`: checkbox after `content_valign`, label, help text; absent from POST = keep stored value
- [x] 3.2 `section_detail_form.html`: show only for the Map stage
- [x] 3.3 Catalog strings for the offered languages (+ `.mo`)

## 4. Travel

- [x] 4.1 ZIP export + boolean import
- [x] 4.2 REST `SectionIn` / `SectionOut`, `forms_bridge`, `out.section`; MCP description; regenerate references

## 5. Tests

- [x] 5.1 Rendering: `panel-keep` class and data attribute on a map section; none by default, on image/form sections
- [x] 5.2 Editor: checkbox saves; POST without it keeps the stored value; live edit in place
- [x] 5.3 Draft copy + ZIP carry it; legacy archive → off
- [x] 5.4 API PATCH + MCP `update_section`
- [x] 5.5 Run the touched modules

## 6. Docs

- [x] 6.1 Help `how-to/lay-out-a-section.md`
- [x] 6.2 The epic's card, with a screenshot (owner, 2026-10-28): `2026-10-29-survey-layout-options.html` + `img/changelog/2026-10-29-survey-layout-options.png` REPLACES `2026-10-28-section-layout.html` — a new id, because creators who saw the old card would never see an edit to it; still one card per epic
- [x] 6.3 CLAUDE.md section-layout paragraph
