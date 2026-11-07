## Context

After #542 a workspace style is `MapStyle` + immutable `MapStyleVersion`s; `survey/map_styles/generator.py::apply_settings(base, settings)` builds a Mapbox GL style from a settings document; `survey/map_styles/tasks.py::publish_map_style_version` creates the hosted style; surfaces resolve keys through `survey/basemaps.py` with pins. ADR 0001 measured the vector path: MapLibre on the respondent page is too heavy, but on the editor page a settings change repaints in about a second, and the print pipeline needs a hosted copy anyway. The measurement prototype (#541, branch `feat/map-styles-render-proto`) already rewrote a generated style for MapLibre: `mapbox://` glyphs, sprite and sources to `https://api.mapbox.com/...?access_token=<public>`; fog/projection/terrain dropped.

## Goals / Non-Goals

**Goals**: a creator edits a style with bounded controls, sees the result at once, sees how it prints, and saves a version that reaches respondents only through the pinning rule. No new Mapbox state until Save.

**Non-Goals**: per-layer editing, fonts, sprites, custom tile sources, reference layers in the preview (the survey frame is enough to judge a base map), mobile-first editing (it must work on a phone, not shine), undo history beyond the browser's.

## Decisions

### D1. The editor is a workspace page on `base.html`
`/org/<slug>/map-styles/<uuid>/edit/`, sidebar active on *Map styles*, roles owner/admin/editor (viewers see the library only). Presets have no editor: *Duplicate* first. The page loads MapLibre GL 5.6 and its CSS from unpkg in `extra_head`, like the library page loads HTMX; nothing else in the app loads MapLibre (the `map-style-rendering` scan test keeps `survey/` free of it except this template and its script, which the test now allow-lists by path).

### D2. Preview endpoint, not inline JSON
`POST /org/<slug>/map-styles/<uuid>/preview.json` with `{settings}` → `survey/map_styles/preview.py::maplibre_style(settings, base)`: `apply_settings`, then `for_maplibre(style, token)` (the prototype's rewriting as a pure function, unit-tested). The base style is fetched with the PUBLIC token (styles:read is on it) and cached a day under the same key the task uses; a fetch failure answers 503 and the page says the preview is unavailable. The endpoint is role-gated and CSRF-protected; it stores nothing. Debounced 300 ms on the client; `map.setStyle(style, {diff: true})` keeps the camera.

### D3. Controls are a fixed schema the client and server share
`survey/map_styles/controls.py::CONTROLS` describes every control (key, kind, options/palettes, default) and `clean_settings(raw)` validates a posted document against it: unknown keys dropped, colours must be `#rrggbb`, enums must be in the list. The template renders the controls from `CONTROLS`; the JS reads the same list from a JSON block. Palettes: six swatches per role (land: whites and warm greys; parks: four greens, two neutrals; water: blues and teals; boundaries: greys; labels major/minor: blacks and greys). A hex input per role takes any colour. Road presets map to `roads.fill / minor_low_zoom / casing` triples (light: white / #e8e8e8 / #c8c8c8; medium: white / #bdbdbd / #8f8f8f — Paper A; strong: white / #9a9a9a / #3a3a3a). Labels: `major`, `minor` palettes, `halo` fixed white, `bold_roads` toggle. `place_names_maxzoom` 6–16.

### D4. Contrast warnings in the browser, greyscale
`greyLuminance(hex)` (Rec. 709 as in the generator); for parks, water, road casing and both label colours against land, a difference below 0.12 shows "hard to tell apart on a photocopy" under the control. Warnings never block Save.

### D5. Save is a version, published like a duplicate
`POST .../save/` with name + settings → `clean_settings`, rename, `MapStyleVersion(number=last+1, settings, pending)`, enqueue publish, event `map_style_saved`. Gate: `require_feature('map_styles')` (plan, or trial with remainder) — editing is Pro like creating, but a Save does not consume the trial allowance (the allowance counts styles, not saves). While the latest version is pending, Save is disabled and the page polls the status every 3 s. The print tab always shows the latest **ready** version.

### D6. Re-pin on live base-map edits
`services.surveys.update_settings` and `services.sections.set_map` call `basemaps.pin_latest(survey)` when the survey is live (`locks.is_live`) and the basemap fields were among the saved data; the pin is what a respondent then sees, so a later editor Save cannot move it. Non-live surveys keep no pins (unchanged).

### D7. Print tab
The frame of the picked survey (`static_map.resolve_frame` for its head section, or the start position) rendered by Static Images at `900x550@2x` with `fresh=true` and the public token, for the latest ready version's style id. A CSS `filter: grayscale(1)` toggle "as a photocopy". If the latest version is pending/failed or there are unsaved changes, a banner says the print view lags behind.

## Risks / Trade-offs

- [MapLibre cannot read a Mapbox `mapbox://` sprite with an unrestricted path] → the rewrite points at `https://api.mapbox.com/styles/v1/mapbox/streets-v12/sprite?access_token=`, which worked in the prototype; a test fixes the shape.
- [Vector tile cost from editing sessions] → a session is ~12 tiles per view; the first paid tier is $0.25/1000; no mitigation needed, noted in the ADR's appendix.
- [A creator saves ten versions in a minute] → the queue's 40/min rate limit paces publishing; each Save is one write; Save is disabled while one is pending.
- [Public token URL restriction blocks the preview on a non-production host] → previews already serve tiles with it; the editor fails the same way the respondent map would.
- [Old versions pile up in Mapbox] → versions no survey pins and that are not the latest are deleted by a sweep in #544's follow-up (out of scope here; counted in the ADR consequences).

## Migration Plan

No schema change. Deploy as part of the epic.

## Open Questions

- Should the preview carry the picked survey's reference layers? Deferred: a base map is judged without them; revisit after the first real styles.
