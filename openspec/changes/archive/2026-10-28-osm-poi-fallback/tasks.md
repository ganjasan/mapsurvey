# Tasks

## 1. Provider-agnostic result shape

- [x] 1.1 Introduce one internal result object — `{name, place, category, lat, lng, bounds, zoom,
      source}` — and make `render()` and `select()` read only that, so neither knows which provider
      answered.
- [x] 1.2 Move the current Mapbox field reading into an adapter (`fromMapbox`). No behaviour change:
      `name`/`full_address`, `place_formatted`, up to two `poi_category` entries, `bbox` when
      present, `feature_type` → zoom.

## 2. Photon adapter

- [x] 2.1 `fromPhoton`: `name`; place line assembled from `housenumber`/`street`/`postcode`/`city`/
      `country`; category from `osm_value` with underscores replaced.
- [x] 2.2 **`extent` is `[west, north, east, south]`, not a GeoJSON bbox** — convert explicitly to
      Leaflet `[[south, west], [north, east]]`. Getting this wrong mirrors the viewport silently.
- [x] 2.3 Zoom fallback when there is no extent: POI-scale (17), street-scale for `osm_key=highway`
      without a name-bearing type.
- [x] 2.4 Language: send `lang` only when it is one of `de`, `en`, `fr`; omit otherwise. Photon
      answers **HTTP 400** on unsupported codes — never pass the respondent's language through blind.

## 3. Fallback and merge

- [x] 3.1 Trigger: no result's name starts with the query's first word. "No POI in the response"
      was tried first and is not enough — "Mercado Central BH" returns holiday rentals named after
      the market, which are POIs and useless. Leading-word, not substring, for the same reason.
- [x] 3.2 Keep only OSM features with a `name` whose `osm_key` is not `place` or `boundary`.
- [x] 3.3 Drop any OSM feature whose coordinates round to the same 3 decimals as a result already in
      the list.
- [x] 3.4 Append at most three OSM results, ordered before the primary ones.
- [x] 3.5 Bound the wait at 1.5s with a `Promise.race` against a timer, not an `AbortController`
      alone — abort assumes the transport honours the signal; a never-settling fetch hung the list
      indefinitely in testing. Abort still fires to stop the request.
- [x] 3.6 Cache the merged list under the existing cache key so a repeated query costs neither
      provider a request.

## 4. Attribution

- [x] 4.1 Footer row on the result list, shown only when the list contains OSM-derived results:
      "© OpenStreetMap contributors", linking to openstreetmap.org/copyright.
- [x] 4.2 Style it in `main.css` and in the editor's scoped block in `survey_create.html`; it must
      read as a footnote, not as a selectable result.
- [x] 4.3 Build it with DOM methods and `textContent` — no `innerHTML`.

## 5. Verification

- [x] 5.1 The cases that motivated this, on a live map: "Ошский рынок", "ЦУМ Бишкек",
      "Mercado Central BH", "東京都庁" each return the real place.
- [x] 5.2 No regression in Jena: "Sportschwimmhalle Jena" and "JenTower" still resolve through
      Mapbox, unchanged.
- [x] 5.3 Addresses unchanged: "Wagnergasse 25 Jena" still returns the address first.
- [x] 5.4 "Bishkek" does not produce two city rows — the OSM `place:city` is filtered out.
- [x] 5.5 Attribution appears exactly when an OSM row is present, and not otherwise.
- [x] 5.6 Fail-open: with the Photon host blocked, searching behaves exactly as before, no console
      error surfaced to the respondent, no hang beyond 2s.
- [x] 5.7 A Portuguese-language survey does not send `lang=pt` (which would 400) and still gets
      results.
- [x] 5.8 Selecting an OSM result moves the map and creates nothing — no marker, no answer.
      Verified on a live survey: "Ошский рынок" → map at 42.8773,74.5706 z17, markers 0,
      editableLayers 0, drawbar hidden.
- [x] 5.9 `python manage.py collectstatic`.
- [x] 5.10 `./run_tests.sh survey` — one run.
