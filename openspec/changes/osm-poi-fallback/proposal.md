## Why

`place-search-poi` (PR #57) gave the search points of interest. Measuring it afterwards showed the
coverage is regional, and sharply so. With `proximity` on Bishkek:

| query | Mapbox Search Box | Photon (OSM) |
|---|---|---|
| Ошский рынок | a street called "Markt" | Ошский рынок, Бишкек |
| ЦУМ Бишкек | the city, and a street | ЦУМ, Бишкек |
| Ala-Too Square | "Market Square" | Площадь Ала-Тоо, Бишкек |
| Mercado Central BH | "Apto Dallas I Raul Soares Centro Merca" | Mercado Central |
| Praça da Liberdade | a street | Praça da Liberdade (park) |
| 東京都庁 (Tokyo city hall) | "東" (a neighborhood) | 東京都庁 (townhall) |
| 上野公園 | a neighborhood | 上野公園 (park) |

Everything tested in Jena resolved through Mapbox. Nothing tested in Bishkek did, and Belo Horizonte
and Tokyo were mostly wrong too — while OSM knew all of them, because the people who map those
cities map them in OSM.

This is not an edge case for us. Belo Horizonte is where our most active user of the last month
works (`docs/marketing/user-outreach/adami/`), Tokyo is RPI Inc., and Bishkek is our own heat-map
project. A respondent there types the name of the market they mean and gets a street with a vaguely
similar name — which reads as "the search is broken", the exact complaint that started this whole
line of work.

## What Changes

- When the geocoder returns **no points of interest** for a query, the search SHALL consult an
  OpenStreetMap-backed geocoder (Photon) and add the points of interest it finds.
- OSM results SHALL be added, never substituted: addresses and settlements keep coming from Mapbox,
  which resolves them better and in more languages.
- Only genuine places SHALL be taken from the fallback — administrative units (cities, districts,
  countries) SHALL be ignored, since those are what Mapbox already answered with.
- A result already present from the primary provider SHALL NOT be duplicated by the fallback.
- Where results derive from OpenStreetMap, the list SHALL carry the attribution ODbL requires.
- The fallback SHALL fail open: if it errors, times out, or returns nothing, the respondent sees
  exactly the results they see today.
- Everything else is unchanged: the search still only moves the map, still records nothing, still
  stays throttled, still disappears without a Mapbox token.

Not in scope: replacing Mapbox (its addresses and its language coverage are better — Photon supports
only `default, de, en, fr` and returns **HTTP 400** on anything else); self-hosting Photon; using the
fallback for addresses or reverse geocoding.

## Capabilities

### Modified Capabilities

- `map-place-search`: the POI requirement gains a second source and the conditions under which it is
  consulted, plus the attribution and fail-open guarantees. View-only behaviour, throttling, and
  absence-without-credentials are untouched.

## Impact

- `survey/assets/js/components/map_place_search.js` — a provider-agnostic result shape, the Photon
  client, the merge, and the attribution row. The file grows; the two provider adapters stay
  separate so either can be swapped.
- `survey/assets/css/main.css` and the editor's scoped block in `survey_create.html` — attribution
  row styling.
- Requires `collectstatic`.
- No model change, no migration, **no new credential** — Photon's public instance needs no key.
- New runtime dependency on `photon.komoot.io`, consulted only when Mapbox finds no POI. It has no
  SLA; the fail-open path is what makes that acceptable, and self-hosting is the escalation if the
  dependency ever matters more than it does now.
- Adds an OSM/ODbL attribution obligation to the search UI. The map tiles already carry OSM
  attribution, so this is a second place to say it, not a new legal position.
