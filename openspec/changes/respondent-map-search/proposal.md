## Why

A creator frames their survey's map with a place search — types "Jena", the map flies there, that
becomes the start position (`survey/templates/editor/survey_create.html:114-292`). Then they open
the published survey and the search is gone. The respondent map
(`survey/templates/base_survey_template.html:149-201`) is built with a zoom control, a base-map
switcher and a "Locate me" button, and nothing else. Grep confirms it across the repo: `nominatim`
and `map-search` occur in exactly one file, the creation page.

Creators have complained about precisely this asymmetry. It is not a regression — respondent search
was never built — but the editor teaches the feature and the survey withholds it.

The respondent is the one who needs it more. A creator frames a map once, deliberately, and can drag
and zoom at leisure. A respondent lands on someone else's viewport and has to answer "where do you
experience the most heat?" — about *their* street, which may be off-screen. Their alternatives today
are "Locate me" (wrong when the question is about somewhere they are not, and a permission prompt
besides) or pan-and-zoom on a phone. Both are worse than typing an address.

Every incumbent we have profiled has this. Open Point does address search via Google Places / Mapbox
Geocoding (`docs/marketing/competitors/openpoint.md:91`); Ideenkarte — the confirmed incumbent at
ThINK Jena — ships a Nominatim geocoder in a PHP site built in the 2010s
(`docs/marketing/user-outreach/mw_think_jena/2026-07-31_call-notes.md:98`). This is table stakes,
not differentiation.

The two surfaces should also not use two different geocoders. Today the editor calls public
Nominatim directly from the browser. Its usage policy caps an entire application at roughly one
request per second and forbids per-keystroke autocomplete — survivable for a handful of creators
framing maps, not for respondent traffic (see the lecture-hall burst the k6 harness in `loadtest/`
reproduces). Worse, a block lands on the whole platform: exceed the limit with respondents and the
creators' search dies with it. Mapbox is already the tile provider, its token is already in settings
and already reaches every template through the context processor
(`mapsurvey/settings.py:258-259`, `survey/context_processors.py:8-9`).

## What Changes

- The respondent map SHALL carry a place search, on every survey, with no configuration. A creator
  who publishes today gets it without touching their survey.
- Searching SHALL move the map only. It never drops a pin, never creates an answer, and never
  touches a geo field — placing the marker stays a deliberate act by the respondent.
- Both surfaces — the respondent map and the creation page — SHALL use one geocoding client, one
  provider, one behaviour: Mapbox Geocoding, with debounced autocomplete and a result list rather
  than the editor's current blind "first hit wins on Enter".
- The editor's direct Nominatim call is removed.
- Where the platform cannot geocode (no `MAPBOX_ACCESS_TOKEN` — self-host, local dev), the search
  control SHALL be absent rather than present and broken.

Not in scope: reverse geocoding (storing a street address for a submitted point — that is the
accessibility item from the ThINK call and its own change, and it would also push us onto Mapbox's
permanent-storage terms); geocoder-driven restriction of where a respondent may answer (Open Point's
"mask layers"); search across the survey's own answers; making search a per-survey toggle — decided
against, see Design.

## Capabilities

### New Capabilities

- `map-place-search`: how a place search behaves on any Mapsurvey map — respondent-facing and
  creator-facing — what selecting a result does and does not do, and how the surface degrades when
  no geocoder is configured.

## Impact

- `survey/assets/js/components/map_place_search.js` — new, the shared control. Built as a Leaflet
  control so both maps mount it identically. Requires `collectstatic` (see the static-files rule in
  `CLAUDE.md`: edit under `survey/assets/`, never `staticfiles/`).
- `survey/assets/css/main.css` — control styling; on desktop the respondent map's left sidebar
  (`#info_page`, 420px, `main.css:76-96`) overlaps Leaflet's top-left corner, so the control needs a
  position that survives both the sidebar and its hidden state.
- `survey/templates/base_survey_template.html` — mount the control after map init (~line 201).
- `survey/templates/editor/survey_create.html` — drop the inline Nominatim block (lines 36-42,
  114-117, 270-292), mount the shared control, keep the existing "framing sets the start position"
  behaviour.
- No model changes, no migration, no new environment variable.
- **Touches an unarchived change.** `simplify-survey-create` is complete but not archived, and its
  delta spec pins the editor's geocoder in prose: "no API key required — OpenStreetMap Nominatim"
  (`openspec/changes/simplify-survey-create/specs/survey-editor/spec.md:49-52`). If it archives
  unamended, that sentence lands in the main `survey-editor` spec already false. This change fixes
  that line in place; whoever archives first wins, and the loser rebases.
- Mapbox geocoding requests carry the respondent's typed query to a US provider. The platform
  already sends every respondent's IP to Mapbox for tiles, so this adds a data *type*, not a new
  processor — but it is one more thing to name when a German buyer asks
  (`openspec/backlog/feature-eu-data-hosting-option.md`). Mapbox appears in no privacy or DPA text
  today; that gap is pre-existing and tracked separately, not fixed here.
