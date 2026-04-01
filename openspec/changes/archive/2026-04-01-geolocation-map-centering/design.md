## Context

`SurveySection` has `start_map_postion` (PointField) and `start_map_zoom` (IntegerField) for map initialization. The Leaflet map in `base_survey_template.html` calls `L.map().setView()` with these values. No browser geolocation code exists. The landing page iframe has `allow="geolocation"` but it is unused.

## Goals / Non-Goals

**Goals:**
- Section-level toggle to enable browser geolocation
- Auto-center map on respondent's position at page load
- "Locate me" button for re-centering
- Visual indicator (blue dot) for user's position
- Graceful fallback to configured position on denial/error

**Non-Goals:**
- Continuous location tracking / watch position
- Storing respondent's geolocation server-side
- Geofencing or location-based question filtering

## Decisions

### 1. Section-level BooleanField (not survey-level)

Different sections may need different map behavior — one section might show a fixed overview area, another might need to center on the user. Matching the granularity of existing map settings (`start_map_postion`, `start_map_zoom`).

### 2. Zoom level 13 on geolocation success

User chose "city" level zoom. The configured `start_map_zoom` is NOT used when geolocation succeeds — zoom 13 provides a consistent experience across all geolocated sections.

### 3. Leaflet custom control for "Locate me" button

Use `L.Control.extend()` to create a standard Leaflet control button in the bottomright position (matching existing zoom control placement). Button uses safe DOM methods (no innerHTML) to avoid XSS.

### 4. CircleMarker for position indicator

Blue circle marker (radius 8, fill #4285F4, white border) — distinct from survey point markers (red Leaflet default markers) and lightweight.
