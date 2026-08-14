# Tasks

## 1. Switch the geocoding call

- [x] 1.1 In `survey/assets/js/components/map_place_search.js`, point `ENDPOINT` at
      `https://api.mapbox.com/search/searchbox/v1/forward`.
- [x] 1.2 Keep `q`, `access_token`, `limit`, `proximity`, `language`, and send `auto_complete=true`
      — measured: without it "Sportschwimmhalle Jena" returns only settlements named Jena, with it
      the pool comes first. "Name then city" is how respondents type.
- [x] 1.3 Verify the response shape against the live API: `features[].properties` must still carry
      `name`, `place_formatted` / `full_address`, `feature_type`, and `geometry.coordinates`, so
      `describe()` and result selection need no change.
- [x] 1.4 Confirm `bbox` still arrives on settlement-scale results, so `fitBounds` keeps working;
      POIs fall through to `flyTo` at the `poi` zoom already in the table.

## 2. Show the POI category

- [x] 2.1 Read `properties.poi_category`; display up to **two** entries joined by "·", underscores
      replaced by spaces. Two, because the array is not ordered specific-first — a park arrives as
      `["outdoors", "park"]`, so taking one would label the park "outdoors". Render nothing when
      absent or empty — no placeholder. The provider localises these to the `language` we send.
- [x] 2.2 Style the category line in `survey/assets/css/main.css`, distinct from the name and the
      place line; must not break the editor's scoped overrides in `survey_create.html`.
- [x] 2.3 Build the row with DOM methods and `textContent`, never `innerHTML` — provider strings are
      untrusted input.

## 3. Verification

- [x] 3.1 The regression that started this: a named POI plus a city resolves to the POI.
      "Sportschwimmhalle Jena" → the pool first, then the settlements. Note "Paradiespark Jena"
      still fails — Mapbox holds that park as "Jena Paradies", which does resolve; POI coverage is
      not the same as knowing every colloquial name.
- [x] 3.2 Addresses still resolve: "Wagnergasse 25 Jena" returns the exact address.
- [x] 3.3 A settlement still uses `fitBounds` (a city fills the viewport rather than zooming to 17).
- [x] 3.4 Selecting a POI moves the map and creates nothing — no marker, no answer, `editableLayers`
      still empty.
- [x] 3.5 Category line renders for POIs and is absent for addresses.
- [x] 3.6 Throttling unchanged: typing a query fires one request, not one per keystroke.
- [x] 3.7 `python manage.py collectstatic`.
- [x] 3.8 `./run_tests.sh survey` — one run.
