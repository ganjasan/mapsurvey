# Simplify the Create New Survey page

## Why

The create page currently dumps the entire `SurveyHeaderForm` on the user —
redirect URL, available languages, visibility, thanks HTML (a JSON blob!),
cover image, basemap checkboxes — plus the map picker. At creation time none
of these decisions can be made meaningfully (the survey has no content yet),
and every one of them is already editable later in the Build space's
"Survey settings" panel. The page reads as a pile of unrelated fields with no
sequence of actions ("нет последовательности действий и понимания что это и
зачем" — user feedback, 2026-07-04).

## What Changes

- The Create New Survey form asks only the foundational things: **what is it
  called** (name), **which languages** it runs in (the shared language picker),
  and **the map people will see**.
- The map block is reframed from the opaque "Where is your survey area?" to
  **"The map people will see"** — it is really the map respondents open on, and
  it is WYSIWYG: the map **centre** is the start position (a fixed centre pin
  marks it, no click-to-drop marker), kept in sync live so a point is always set
  and the creator sees exactly what respondents will. The base map is chosen via
  an **on-map layers dropdown** (top-right, icons) that sets `default_basemap`
  using the same tile providers respondents get (Mapbox / Esri World Imagery /
  OpenTopoMap); all base maps stay enabled. Framing tools: place search
  (OpenStreetMap Nominatim, no key), a "My location" button, and creator
  auto-geolocation that opens the map near them.
- The "Auto-center on respondent's location" toggle is dropped from creation:
  it contradicts the map area just set, is written in jargon
  ("respondent"/"visitor", "browser geolocation on entry"), and already lives
  in Survey settings → Default map position.
- Everything else — redirect URL, visibility, thanks page, cover image, and
  *which* base maps are enabled — is dropped from the form and inherits model
  defaults (`redirect_url="#"`, `visibility=private`,
  `basemaps=streets/satellite/topo`, empty `thanks_html`, no cover). A hint
  under the actions points to Survey settings for them.
- The page is a full-page two-column layout in the shared
  `.pr-card`/`.pr-field`/`.pr-help` vocabulary; the map fills the right column.
- Server-side: a minimal `SurveyCreateForm` (name + `available_languages`)
  replaces `SurveyHeaderForm` in `editor_survey_create`, which also reads
  `default_basemap` from POST (validated against `BASEMAP_CHOICES`); the
  settings panel keeps the full form. No model or migration changes.

## Impact

- Affected specs: `survey-editor`
- Affected code: `survey/editor_forms.py` (new `SurveyCreateForm`),
  `survey/editor_views.py` (`editor_survey_create`),
  `survey/templates/editor/survey_create.html`
- No data changes; existing surveys and the settings panel are untouched.
