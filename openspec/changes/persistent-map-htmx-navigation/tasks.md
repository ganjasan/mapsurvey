## 1. Model Changes & Migration

- [ ] 1.1 Add `SurveyHeader.default_basemap` CharField(nullable, choices=BASEMAP_CHOICES)
- [ ] 1.2 Add `SurveyHeader.start_map_postion` PointField(nullable) and `SurveyHeader.start_map_zoom` IntegerField(nullable)
- [ ] 1.3 Make `SurveySection.start_map_postion` nullable (allow null = don't change)
- [ ] 1.4 Make `SurveySection.start_map_zoom` nullable (allow null = don't change)
- [ ] 1.5 Add `SurveySection.override_basemap` CharField(nullable, choices=BASEMAP_CHOICES)
- [ ] 1.6 Create migration 0029
- [ ] 1.7 Update serialization.py: export/import new fields
- [ ] 1.8 Update versioning.py: clone/publish new fields

## 2. Shell Infrastructure

- [ ] 2.1 Add HTMX script to `base_survey_template.html` head
- [ ] 2.2 Add `window._basemapLayers` to `partials/basemap_layers.html`
- [ ] 2.3 Add `switchBasemap(slug)` function to shell
- [ ] 2.4 Change map init to use `_initialMapState` from context (not section directly)
- [ ] 2.5 Remove `useGeolocation` hardcoded block — move to initSection()

## 3. Extract Section Scripts into Shell Functions

- [ ] 3.1 Move `draw:created` handler from section_scripts into shell, use `window._subquestionsForms`
- [ ] 3.2 Move `onPopupOpen` / `onPopupClose` into shell
- [ ] 3.3 Create `restoreGeoAnswers(answers)` function in shell
- [ ] 3.4 Create `initTracking(sessionId, sectionName, sectionCurrent)` function in shell
- [ ] 3.5 Convert draw button handlers to delegated: `$(document).on('click', '.drawpolygon', ...)`
- [ ] 3.6 Replace `$('#section_question_form').submit(...)` with `htmx:configRequest` handler

## 4. Create Section Partial Template

- [ ] 4.1 Create `survey/templates/partials/survey_section_partial.html`
- [ ] 4.2 Move title/progress/content/navig_buttons HTML into partial
- [ ] 4.3 Add `data-*` scalar attributes on root div
- [ ] 4.4 Add `json_script` blocks for subquestions_forms and existing_geo_answers
- [ ] 4.5 Add `hx-post` to form, `hx-get` to back button, targeting `#section-panel`

## 5. Wire initSection() and Swap Target

- [ ] 5.1 Add `<div id="section-panel">` as HTMX swap target inside `#info_page`
- [ ] 5.2 Write `initSection()`: clearLayers, flyTo, switchBasemap, locateUser, restoreGeoAnswers, initTracking, scrollTop
- [ ] 5.3 Bind `DOMContentLoaded` → `initSection()`
- [ ] 5.4 Bind `htmx:afterSettle` → `initSection()` (guarded by target id)
- [ ] 5.5 Guard first-load flyTo (skip animation on initial render)
- [ ] 5.6 Remove `{% block section_scripts %}` from shell

## 6. Simplify survey_section.html

- [ ] 6.1 Reduce `survey_section.html` to: extends shell + includes partial

## 7. View HTMX Handling

- [ ] 7.1 Extract `_build_section_context()` helper in views.py
- [ ] 7.2 GET: if HX-Request → render partial; else → render full page
- [ ] 7.3 POST: if HX-Request → save answers, render next section partial (or HX-Redirect for last)
- [ ] 7.4 Pass `initial_map_lat/lng/zoom` in full-page context (from first section or survey defaults)
- [ ] 7.5 Pass `existing_geo_answers` as dict (not JSON string) for json_script
- [ ] 7.6 Remove `.replace("/script", "\/script")` from subquestions_forms building

## 8. Editor UI for New Fields

- [ ] 8.1 Add `default_basemap` to survey settings form/template
- [ ] 8.2 Update map picker modal for nullable section position/zoom
- [ ] 8.3 Add `override_basemap` selector to map picker modal

## 9. Tests

- [ ] 9.1 Test: HTMX GET returns partial (no <head>, no map init)
- [ ] 9.2 Test: non-HTMX GET returns full page (has <head>, map init)
- [ ] 9.3 Test: POST via HTMX saves answers and returns next section partial
- [ ] 9.4 Test: POST on last section returns HX-Redirect to thanks URL
- [ ] 9.5 Test: back navigation (HTMX GET) returns previous section with existing answers
- [ ] 9.6 Test: new model fields serialize/deserialize correctly
- [ ] 9.7 Test: clone_survey_for_draft copies new fields
