# Tasks — simplify-survey-create

## 1. Implementation

- [x] 1.1 `SurveyCreateForm` in `survey/editor_forms.py`: `ModelForm` over
      `SurveyHeader` with `fields = ['name']` (same TextInput widget as
      `SurveyHeaderForm`); `SurveyHeaderForm` stays as-is for the settings panel
- [x] 1.2 `editor_survey_create` uses `SurveyCreateForm`; map hidden-field
      handling, owner collaborator, and default first section unchanged; drop
      the now-unused `basemap_choices` from the create context
- [x] 1.3 Rewrite `survey_create.html`: `.pr-card` with the name `.pr-field`
      ("e.g. Park improvements" placeholder), "Where is your survey area?"
      map section (same picker JS), `.pr-switch` for auto-center, Create/Cancel,
      and a `.pr-help` hint pointing to Survey settings for everything else
- [x] 1.4 Full-page layout: the card spans the page (`max-width:1400px`) with a
      two-column grid — left holds name + actions + hint, right holds a tall map;
      collapses to one stacked column below 900px
- [x] 1.5 Drop the confusing "Auto-center on respondent's location" toggle from
      the create page (it contradicts the just-set survey area and is already in
      Survey settings → Default map position); creator auto-geolocation now only
      opens the map near the creator, it does not set a value
- [x] 1.6 Add a place search above the map (OpenStreetMap Nominatim, no key):
      typing a place + Enter recentres the map and sets the start position;
      empty/failed searches show an inline message in the coords line
- [x] 1.7 Add a "My location" Leaflet control (bottom-right, `fa-crosshairs`,
      flex-centered — clear of the base-map dropdown at top-right): clicking
      geolocates and sets the start position; a denied/failed lookup shows an
      inline hint
- [x] 1.8 Add `available_languages` to `SurveyCreateForm` and render the shared
      `language_picker.html` on the create page (languages shape every later
      step, so they are chosen up front, not deferred)
- [x] 1.9 Reframe the map block from "Where is your survey area?" to "The map
      people will see"; add a base-map selector that switches the preview via the
      same providers respondents get (Mapbox/Esri/OpenTopoMap) and posts
      `default_basemap`; the view validates it against `BASEMAP_CHOICES` and
      leaves all base maps enabled
- [x] 1.10 Move the base-map selector onto the map as a custom dropdown control
      (top-right): a compact toggle showing the current base map (icon + name +
      chevron) that opens a click-to-select menu with icons — a real dropdown,
      not the hover-expanded `L.control.layers` radio panel. Selecting an option
      switches the preview layer, writes the slug into the hidden
      `default_basemap`, and closes the menu; clicking outside closes it
- [x] 1.11 WYSIWYG map position: the map CENTRE is the start position (no
      click-to-drop marker). A fixed centre pin overlay marks it; `map_lat/lng/
      zoom` sync from `map.getCenter()`/`getZoom()` on load and on
      `moveend`/`zoomend`, so a point is always set and the picker shows exactly
      what respondents open on. Search / My location / auto-geolocate just
      `setView`; the sync follows

## 2. Verification

- [x] 2.1 Tests: creating with name only yields model defaults
      (visibility=private, redirect `#`, basemaps all three, empty
      thanks/languages) and redirects to Build; map lat/lng/zoom still saved
      when posted
- [x] 2.2 Existing create tests still pass (they post only `name` + map
      fields — now the canonical shape)
- [x] 2.3 Manual: create a survey via the new page, open Survey settings,
      confirm all deferred fields are editable there
