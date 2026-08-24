# Proposal: reference-overlay-layers

## Why

Creators cannot show respondents any spatial context beyond the basemap: counting zones,
a study-area boundary, a planned route. Third independent request (Olney — declined in
writing; Ideenkarte parity; ThINK Jena will ask), and the main honest reason a
municipality would pick Survey123 over us. The "park renewal plan" case adds a second
role for the same mechanism: the overlay as the *subject* respondents comment on.

Scoping decisions (2026-08-25, discussed with owner): vector GeoJSON only (raster plan
→ backlog #147), upload only (drawing in editor → backlog #148), layers stored on the
survey with per-section visibility, per-feature identity (key field) baked into the data
model now so FD-14 ("map follows the answer") needs no migration later.

## What Changes

- New `SurveyMapLayer` model: a creator uploads a GeoJSON (≤10 MB, WGS84) that renders
  as a non-editable overlay under the respondent map. Config per layer: name, color
  (fallback — simplestyle properties in the file win), label field, key field, info
  popups on/off.
- Respondent map renders the survey's layers beneath answer geometry; each layer is
  toggleable via the existing Leaflet layers control; overlay features never intercept
  the tap-to-answer flow (info popups, when enabled, are the only interaction).
- Sections choose which layers show on their map (checklist in the section form,
  default: all) — the override-basemap pattern. Layers survive HTMX section swaps via
  `initSection()`.
- Layer GeoJSON is served by a dedicated cacheable endpoint under the survey namespace
  (not inlined in the template, not a raw storage URL).
- Editor: "Reference layers" card in Survey settings (upload zone + layer cards);
  "Reference layers" checklist in the section form.
- ZIP export/import round-trips layers (`survey.json → layers[]` + `layers/*.geojson`).
- Kill switch: `MAP_REFERENCE_LAYERS` env flag (default on); off hides the editor UI
  and stops respondent rendering.

## Capabilities

### New Capabilities

- `reference-overlay-layers`: layer lifecycle (upload, validate, configure, delete),
  respondent rendering rules (styling, labels, popups, non-interference, toggling,
  per-section visibility), and the delivery endpoint.

### Modified Capabilities

- `survey-editor`: Survey settings gains the Reference layers card; the section form
  gains the per-section layer checklist.
- `survey-serialization`: `layers[]` join the archive format and round-trip.

## Impact

- `survey/models.py` — new `SurveyMapLayer`; `SurveySection.hidden_layers` (JSON).
- `survey/views.py` — layer GeoJSON endpoint; map context gains layer metadata.
- `survey/templates/base_survey_template.html`, `partials/basemap_layers.html`,
  `partials/survey_section_partial.html` — overlay rendering + section visibility.
- `survey/editor_views.py`, `editor/partials/survey_settings_panel.html`,
  `editor/partials/section_detail_form.html` — editor UI + endpoints.
- `survey/serialization.py` — export/import hooks (S3-safe file reads).
- New migration (check leaf numbering against parallel worktrees before merge).
