## Context

Survey section navigation uses full page reloads. Each section = new page, new map init, new tile download. Map position, zoom, and basemap reset on every transition. `base_survey_template.html` is the shell with map + draw infrastructure. `survey_section.html` extends it with form content and section-specific scripts.

The editor already uses HTMX extensively for partial loading (sections, questions, modals) with persistent layout.

## Goals / Non-Goals

**Goals:**
- Map persists across section transitions — no re-initialization, no tile re-download
- Section content swaps via HTMX into a target container
- Survey-level defaults for map position/zoom/geolocation/basemap
- Section-level optional overrides (null = keep current state)
- Drawn features cleared between sections, saved answers restored
- Backward compatible: direct URL access still works (full page render)

**Non-Goals:**
- SPA routing / browser history management (URL stays on current section)
- Offline support
- Animation library for map transitions (use Leaflet's built-in flyTo)
- Changing the editor map picker UI (separate follow-up)

## Decisions

### 1. Persistent Shell + HTMX Swap Target

**Decision**: `base_survey_template.html` becomes a persistent shell. A `<div id="section-panel">` inside `#info_page` is the HTMX swap target. New `partials/survey_section_partial.html` contains all swappable content.

**Rationale**: Minimal change to existing structure. Map, draw controls, crosshair all stay in shell unchanged. Only the section-specific content moves to a partial.

### 2. No executable scripts in partial — data via json_script + data attributes

**Decision**: The partial contains zero executable script tags. Complex data (subquestions_forms, existing_geo_answers) passed via Django's `json_script` filter. Scalar config (lat, lng, zoom, basemap, sessionId) via `data-*` attributes.

**Rationale**: HTMX does not execute script tags in swapped content. `json_script` renders `<script type="application/json">` which HTMX inserts into DOM (readable via `.textContent`) but does not execute. Data is parsed via `JSON.parse()` in the shell's `initSection()` function.

### 3. initSection() orchestrator

**Decision**: Single `initSection()` function in the shell, called on DOMContentLoaded (first load) and htmx:afterSettle (subsequent swaps). Handles: clear editableLayers, flyTo, switchBasemap, locateUser, restore geo answers, init tracking, scroll to top.

**Rationale**: Centralizes all post-swap logic. Each concern is a simple block reading from data attributes / json_script elements.

### 4. Delegated event handlers for draw buttons

**Decision**: `$(document).on('click', '.drawpolygon', ...)` instead of `$('.drawpolygon').click(...)`.

**Rationale**: Draw buttons are inside the swapped content. Direct binding only works for elements present at page load. Delegated handlers work for dynamically inserted elements.

### 5. Form POST via hx-post, view returns next section partial

**Decision**: Form gets `hx-post` targeting `#section-panel`. View saves answers, then renders next section's partial as response. For last section: `HX-Redirect` header to thanks page.

**Rationale**: Single POST-and-swap avoids the current POST-redirect-GET triple round-trip. HTMX handles `HX-Redirect` as full-page navigation automatically.

### 6. Geo serialization via htmx:configRequest

**Decision**: Replace `$('#section_question_form').submit(...)` with delegated `htmx:configRequest` handler that serializes editableLayers into .geo-inp hidden inputs before HTMX sends the request. Setting `evt.detail.cancel = true` aborts for validation failures.

**Rationale**: `htmx:configRequest` fires before the XHR. Delegated binding survives swaps.

### 7. Model changes: survey-level defaults + nullable section overrides

**Decision**:
- `SurveyHeader`: add `default_basemap` (CharField, nullable), `start_map_postion` (PointField, nullable), `start_map_zoom` (IntegerField, nullable)
- `SurveySection`: `start_map_postion` becomes nullable, `start_map_zoom` becomes nullable, add `override_basemap` (CharField, nullable)

**Rationale**: Survey-level defaults set the initial map state. Sections optionally override. Null means "keep whatever the respondent currently sees."

### 8. Map position flyTo behavior

**Decision**: If section has non-null position/zoom, call `map.flyTo()` with 0.8s animation. If null, map stays where it is. First section (DOMContentLoaded) sets view without animation.

**Rationale**: Smooth transition when survey author sets a position. No jarring jump when they don't.

## Component Design

### Persistent Shell (base_survey_template.html)

```
<head>: CSS, Leaflet, Leaflet.draw, Bootstrap, jQuery, HTMX, FA
<body>:
  <button id="showButton">
  <div id="info_page">
    <div id="section-panel">
      {% block section_panel_content %}{% endblock %}
    </div>
  </div>
  <div id="drawbar">
  <div id="crosshair-overlay">
  <div id="map">
  <script>:
    - _initialMapState from context
    - L.map init with _initialMapState
    - basemap layers (include partial)
    - geolocation functions
    - draw infrastructure (editableLayers, drawControl, crosshair)
    - delegated handlers (.drawpolygon, .drawline, .drawpoint)
    - draw:created handler (using window._subquestionsForms)
    - onPopupOpen / onPopupClose
    - restoreGeoAnswers()
    - switchBasemap()
    - initTracking()
    - initSection() orchestrator
    - htmx:configRequest for geo serialization
    - DOMContentLoaded -> initSection()
    - htmx:afterSettle -> initSection()
```

### Section Partial (partials/survey_section_partial.html)

```html
<div id="section-data"
     data-map-lat="..." data-map-lng="..." data-map-zoom="..."
     data-use-geolocation="..." data-map-basemap="..."
     data-session-id="..." data-section-name="..." data-section-current="..."
     data-survey-name="...">

  <div class="header">title + close button</div>
  <div class="survey-progress">X / Y</div>
  <div id="content">
    subheading + form (hx-post, hx-target="#section-panel")
  </div>
  <div id="navig_buttons">
    back (hx-get) + next/finish (submit)
  </div>

  {{ subquestions_forms|json_script:"sq-forms-data" }}
  {{ existing_geo_answers|json_script:"geo-answers-data" }}
</div>
```
