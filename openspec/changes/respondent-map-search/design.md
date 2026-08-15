## Context

Two maps, two different amounts of search. The creation page has a text input above the map that
fires one Nominatim request on Enter and takes the first hit
(`survey/templates/editor/survey_create.html:270-292`). The respondent map has nothing
(`survey/templates/base_survey_template.html:149-201`). This change gives both the same control,
and moves the platform off public Nominatim.

Constraints that shaped the decisions below:

- **Mapbox is already here.** `MAPBOX_ACCESS_TOKEN` is in settings (`mapsurvey/settings.py:259`) and
  the context processor puts it in every template (`survey/context_processors.py:8-9`). Six
  templates already interpolate it for tiles. No new secret, no new deploy step.
- **Autocomplete is billed per keystroke.** Mapbox's own docs: with `autocomplete=true` "each
  keystroke counts as an individual API request", and they recommend a character threshold. A
  respondent map is high-traffic by construction, so throttling is not optional.
- **We must not store geocoding results.** Mapbox's default `permanent=false` carries the
  restriction verbatim in every response's attribution: "This response and the information it
  contains may not be retained." Persisting a geocoded address would put us on permanent-storage
  terms and cost more.
- **The respondent map is crowded.** Leaflet's `topright` corner already holds the draw control
  (`base_survey_template.html:258`) and the base-map switcher
  (`partials/basemap_layers.html:27`); `bottomright` holds zoom and "Locate me"
  (`:151`, `:184`). `topleft` is free of Leaflet controls but sits under the 420px section sidebar
  (`main.css:76-96`), which slides out (`#info_page.hidden`, `main.css:98-100`) rather than
  disappearing.

## Goals / Non-Goals

**Goals**

- A respondent can move the map to a named place without granting geolocation and without panning.
- Search never produces an answer — it changes the viewport, nothing else.
- One geocoding implementation for the whole platform.
- The control disappears cleanly where no geocoder is configured.

**Non-Goals**

- Reverse geocoding / storing addresses on answers (permanent-storage terms; separate change).
- Restricting where a respondent may answer using a searched boundary.
- Per-survey on/off switch for search.
- Self-hosting a geocoder, or an EU-resident geocoding endpoint.

## Decisions

### Search is always on, not a per-survey setting

The alternative — a `SurveyHeader` boolean with a checkbox in the editor — was considered and
rejected. It costs a migration, a settings-panel row, and a decision every creator must make; and
the failure mode it protects against does not exist. Search moves a viewport. A creator who wants
respondents confined to one district is not served by hiding search anyway (the map still pans),
and the honest fix for that is a boundary constraint on the *answer*, which is a different feature.
Making it a toggle would also mean the complaint that started this change ("it's in the editor, not
in the survey") reappears as "it's off by default".

Consequence: every published survey gains the control on deploy, with no creator action. That is
the intent — the surveys with the complaint are already live.

### Mapbox Geocoding v6, called from the browser

Endpoint: `GET https://api.mapbox.com/search/geocode/v6/forward`, with `q`, `access_token`,
`limit=5`, `language=<active UI language>`, `proximity=<current map centre>`, and
`permanent` left at its default of `false`.

- **`proximity` matters more than it looks.** A respondent in Jena typing "Bahnhofstraße" — a street
  name that exists in hundreds of German towns — should get theirs. Biasing to the current map
  centre, which is the survey's start position, does that for free.
- **`language`** follows the respondent's active language, so a Russian-language survey does not
  return English exonyms.
- **Called from the browser, not proxied.** A server-side proxy would let us cache and hide the
  token, but the token is already public in the page for tiles, so proxying hides nothing; and a
  proxy would put geocoding latency on our 0.5-CPU Render instance, which the load tests
  (`loadtest/README.md`) say is the scarce resource. Rejected. If per-key abuse becomes real, the
  answer is a URL-restricted token in the Mapbox dashboard, not our own hop.

Nominatim was rejected for respondent traffic on its usage policy alone: ~1 req/s for the whole
application and no per-keystroke autocomplete. Photon (EU-hosted, no key) stays on the table as the
fallback if Mapbox billing surprises us — the client is written behind one function so the swap is
local.

### Cost control: threshold, debounce, cache, abort

Four cheap measures, in the client, in this order:

1. No request under 3 characters.
2. 300ms debounce after the last keystroke.
3. In-memory cache keyed by `(query, rounded proximity)` for the page's lifetime — retyping and
   backspacing are free.
4. `AbortController` on the in-flight request when a new one starts.

Worst realistic case sized against the load-test scenario: a 200-respondent survey where every
respondent searches twice ≈ 400 keystroke-bursts ≈ well under 1,000 requests. Mapbox's free tier is
~100k/month. Cost is not the binding constraint; these measures exist so a pathological client (a
key held down, a bot) cannot make it one.

### Selecting a result moves the map and nothing else

`map.fitBounds(feature.properties.bbox)` when the feature carries a bbox (cities, regions), else
`map.flyTo(coordinates, zoom)` with a zoom chosen from `properties.feature_type` — address/street
land closer than region/country. No marker is dropped, no geo field is written, no draw mode starts.

This is the one behaviour that must not be "helpful". A respondent searching "my street" is
orienting; if the search dropped a pin it would look like an answer was recorded, and on a
single-point question it would silently be one. Placing the point stays an explicit act.

The creation page keeps its existing rule — the map centre *is* the start position, so framing by
search sets it (`simplify-survey-create` spec). That is the map-moved consequence, not a
search-specific one, so it survives untouched.

### One control, two mount modes

`MapPlaceSearch.attach(map, options)` mounts as a Leaflet control by default, and renders into a
supplied `options.container` instead when one is given. The respondent map takes the control form;
the creation page keeps its input above the map, where it already sits inside a settled layout that
`simplify-survey-create` tuned.

The behaviour — geocoder, throttling, result list, keyboard handling, what selecting does — is the
same object in both cases. Only the DOM parent differs. Forcing the editor's input onto the map
would have meant re-tuning that page's layout for no gain to anyone.

### Placement: top-left, offset past the sidebar

The control mounts at Leaflet's `topleft`, with a left offset on desktop that clears the 420px
`#info_page` sidebar, transitioning back when the sidebar is hidden (it already animates via
`transform`, `main.css:88`). On mobile (`max-width: 768px`, the existing `isMobile()` breakpoint at
`base_survey_template.html:127`) the sidebar is a full-width overlay, so the control spans the map
width under the top edge and collapses to an icon until tapped — a permanently-expanded input would
eat scarce vertical space on the surface where panning is worst.

`topright` was rejected: it would sit between the draw toolbar and the base-map switcher, and the
draw toolbar appears and disappears with question type, so the search box would jump.

### Degradation when no token is set

If `MAPBOX_ACCESS_TOKEN` is empty the control is not created at all. Self-hosters and local dev
without a token see the map exactly as today rather than an input that returns 401 on every
keystroke. The editor loses its search in that configuration — today it has one, keyless, via
Nominatim. That regression is accepted: it applies only to deployments with no Mapbox token, where
the tiles are already broken, so the map is unusable regardless.

## Risks / Trade-offs

- **Every geocoding request carries respondent-typed text to a US processor.** Mapbox already
  receives every respondent's IP for tiles, so this adds a data type rather than a new processor,
  but a German public-sector buyer will ask. Mapbox is named in no privacy or DPA text today — a
  pre-existing gap (`openspec/backlog/feature-eu-data-hosting-option.md`), widened slightly here,
  not closed here. Mitigation if it becomes a blocker: Photon, EU-hosted, behind the same function.
- **Billing now scales with respondent traffic, not creator count.** A survey that goes viral could
  move geocoding from free-tier noise to a line item. The four throttles above bound it; the metric
  to watch is Mapbox usage per month against the 100k free tier.
- **Collides with an unarchived change.** `simplify-survey-create` is complete but not archived and
  its delta asserts the editor's geocoder is keyless Nominatim
  (`specs/survey-editor/spec.md:49-52`). Both this change and that one must not archive with
  contradictory prose. Handled as a task here; if that change archives first, this one rebases onto
  the main `survey-editor` spec instead.
- **Mapbox v6 is the third geocoding API Mapbox has shipped** (v5, Search Box, Geocoding v6). The
  client is one function against one endpoint so a forced migration is a contained edit.

## Migration Plan

No data migration, no model change, no new environment variable. Deploy order is irrelevant: the
control is client-side and reads a token that is already being interpolated into these templates.

Static assets are the one operational step — the new JS lives in `survey/assets/js/components/` and
needs `collectstatic`, per the project rule never to edit `staticfiles/` directly.

Rollback is deleting the mount call from the two templates; nothing persists.

## Open Questions

- Should the searched place be logged (query text, not result) to learn what respondents look for?
  Useful signal for the "authors work around gaps silently" problem, but it is respondent-typed free
  text and would need a privacy decision. Deferred, deliberately not in this change.
