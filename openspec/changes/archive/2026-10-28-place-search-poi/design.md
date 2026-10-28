## Context

`map_place_search.js` calls one endpoint from one function, which is what makes this change small.
The decision to be made is which Mapbox search product replaces Geocoding v6, and there are three
candidates with different billing and different call shapes.

Measured on production before this change: "Wagnergasse 25 Jena" → exact address; "Paradiespark
Jena" → five settlements named Jena. Nothing about the client is wrong; the index has no POIs.

## Goals / Non-Goals

**Goals**

- A respondent typing the everyday name of a place — a park, a station, a pool — finds it.
- Addresses keep working exactly as well as they do today.
- The result list makes clear what kind of place each row is.
- One function still owns the network call.

**Non-Goals**

- Category search ("all pharmacies near here").
- Reverse geocoding, ETA, country restriction.
- Any change to what selecting a result does. It still only moves the map.

## Decisions

### Search Box `/forward`, not `/suggest` + `/retrieve`

Search Box offers two ways in:

- **`/forward`** — one request, returns GeoJSON with coordinates. Billed per request.
- **`/suggest` + `/retrieve`** — type-ahead suggestions, then a second call to resolve the chosen
  one. Billed per *session* (a `session_token` groups up to N suggests plus one retrieve into a
  single billable unit).

The session flow is the canonical autocomplete pattern and would be cheaper for a client that fires
on every keystroke. Ours does not: a 3-character floor, a 300ms debounce and a per-page cache. On
production the measured behaviour is roughly one request per search, three at worst for a long slow
query. A session would bill those same three as one unit, but it also costs a second round-trip on
every selection (the respondent waits for `/retrieve` before the map moves), a `session_token` to
generate and carry, and two response shapes to handle instead of one.

Taking `/forward`: same call shape as today, coordinates arrive with the results so selection stays
instant, and the throttles we already have keep request counts near one per search. If respondent
volume ever makes geocoding a real line item, switching to the session flow is a contained change in
the same function — and at that point the measurement will exist to justify it.

### The response is close enough to v6 to keep the same handling

Search Box returns a GeoJSON `FeatureCollection` whose feature properties carry `name`,
`full_address`, `place_formatted`, `feature_type`, and `coordinates` — the same fields the control
already reads. POI features additionally carry `poi_category` and `maki`.

So `describe()` needs no change, and result selection keeps its existing shape: `fitBounds` when the
feature carries a `bbox` (settlements and regions do), otherwise `flyTo` at a zoom chosen from
`feature_type`. `poi` is already in that table at zoom 17, which was speculative when it was written
and is now the common case.

### Show the category, because a name alone is ambiguous

A POI result gets a category chip next to its name. The case is not hypothetical — measured against
the live API with `proximity` on Jena, "Paradies Jena" returns:

| name | place | poi_category |
|---|---|---|
| Jena Paradies | 07743 Jena | `bahnhof, transport` |
| Jena Paradies | 07743 Jena | `draußen, park` |

A railway station and a park, identical names, same postcode, adjacent rows. Without the category
the respondent picks by coin toss.

Mapbox returns `poi_category` as an array; we show the first entry with underscores replaced by
spaces, and nothing at all when the array is empty (addresses, streets, settlements). **The provider
localises the categories to the `language` we already send** — the table above came back in German
because the request said `language=de`. So no mapping table and no translation work on our side, and
categories arrive in the respondent's language for free.

### `auto_complete=true`, contrary to first instinct

The plan was to leave it off: the debounce means queries arrive complete, and partial matching
sounded like noise. Measured against the live API, that was wrong — the flag is what makes the most
natural query shape work at all.

| query | `auto_complete` off | `auto_complete=true` |
|---|---|---|
| "Sportschwimmhalle Jena" | Jena, Jena, Jena (settlements) | **Sportschwimmhalle Schwimmparadies**, then the settlements |
| "Sportschwimmhalle" | the pool | the pool |
| "Botanischer Garten Jena" | two rentals | two rentals |

"Name of the place, then the city" is exactly how a respondent types, and without the flag the
provider falls back to matching the city alone. On, then.

What it does not fix: a **generic** term plus a city — "Schwimmbad Jena" ("swimming pool Jena")
returns settlements either way, because it is a category, not a name. Finding places by category is
the `/category` endpoint's job and is out of scope here.

## Risks / Trade-offs

- **POIs make the result list less predictable.** Searching a street name in a dense city can now
  return a shop on that street above the street itself. Measured example: "Botanischer Garten Jena"
  returns two holiday-rental listings named after the garden, with empty categories, and not the
  garden. `proximity` still biases to the survey's map and the category chip tells the respondent
  what they are looking at, but the ordering is the provider's and we do not control it. This is the
  price of POIs being in the index at all, and it is worth paying — the alternative is the current
  state, where the park cannot be found by any spelling.
- **A place is only findable under the name the provider knows.** "Paradiespark Jena" still returns
  nothing useful, because Mapbox holds that park as "Jena Paradies". POI coverage moves the ceiling;
  it does not make every colloquial name work.
- **Mapbox's POI coverage is strongly regional, and this is the significant limitation.** Measured
  with `proximity` on Bishkek:

  | query | Mapbox Search Box | Photon (OSM) |
  |---|---|---|
  | Ошский рынок | a street called "Markt" | Ошский рынок, Бишкек |
  | ЦУМ Бишкек | the city, and a street | ЦУМ, Бишкек |
  | Ala-Too Square | "Market Square" | Площадь Ала-Тоо, Бишкек |
  | Osh Bazaar | Oshin Hotel, Osho Garments | — |

  Everything tested in Jena resolved correctly; nothing tested in Bishkek did. Our German
  public-sector cases are well served, our own Bishkek heat-map project would not be. The lever, if
  we want it, is a fallback to an OSM-backed geocoder when Mapbox returns no POI — deliberately not
  taken here, because it means a second provider, a second response shape, and an ODbL attribution
  obligation, and that deserves its own change.
- **A second provider surface to depend on.** Search Box is a different product from Geocoding, with
  its own deprecation clock; Mapbox has now shipped three generations of search API (v5, v6, Search
  Box). The one-function containment is the mitigation, and it is the reason this change is a
  three-line edit rather than a rewrite.
- **Billing is still per-request and still scales with respondent traffic** — unchanged from the
  current situation, and the existing throttles are what bound it.
- **No new privacy surface.** Same provider, same token, same account, same US processing. The query
  text already went to Mapbox before this change.

## Migration Plan

Client-side only. Deploy is the deploy; there is no state to migrate and nothing to backfill. Static
assets need `collectstatic`. Rollback is reverting the endpoint constant and the two parameters.

## Open Questions

None blocking. If the noisier ordering turns out to bother creators, the lever is `types` (restrict
or rank the feature types we ask for) rather than going back to an index without POIs.
