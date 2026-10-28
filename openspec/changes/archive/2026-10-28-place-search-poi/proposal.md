## Why

The place search shipped yesterday (`respondent-map-search`, PR #56) finds addresses and
settlements and nothing else. Verified on production: "Wagnergasse 25 Jena" resolves to the exact
address, while "Paradiespark Jena" returns *cities named Jena* — the park is not in the answer set
at all.

That is the Geocoding v6 data model, not a bug: it indexes addresses, streets, postcodes, places,
regions, countries. Points of interest are absent by design.

Points of interest are how respondents actually name places. Our own demo survey asks "wo trifft Sie
die Hitze?" and "wohin gehen Sie, um sich abzukühlen?" — the honest answers are a park, a square, a
swimming pool, a library, a shopping centre, a station. A respondent types the name they use in
conversation, gets five cities called Jena back, and concludes the search is broken. The same holds
for the live surveys in our base: community meeting places, avoided places, places you go in your
routine — all named as POIs, none findable today.

The address search we shipped is not wrong, it is half the feature.

## What Changes

- The place search SHALL find points of interest — named parks, squares, stations, venues, shops,
  public buildings — in addition to the addresses and settlements it finds today.
- A result SHALL show what kind of place it is where the provider says so, since "Paradiespark" as a
  park and "Paradiespark" as a street are different answers to the respondent's question.
- The geocoding call moves from Mapbox Geocoding v6 (`/search/geocode/v6/forward`) to the Mapbox
  Search Box forward endpoint (`/search/searchbox/v1/forward`), which serves POIs, addresses and
  places from one query. Same token, same account, same `proximity` / `language` / `limit`
  parameters.
- Everything else about the search is unchanged and stays specified as it is: it moves the map view
  and nothing else, it never records an answer, it stays throttled, it is absent without a token.

Not in scope: category browsing (`/category` — "show me all pharmacies"), reverse geocoding,
ETA-annotated results, or restricting results by country. The suggest/retrieve session flow is
considered and rejected below.

## Capabilities

### Modified Capabilities

- `map-place-search`: the requirement that the search finds places gains points of interest; the
  provider-specific requirement changes endpoint. The behavioural requirements — view-only, no
  stored results, bounded requests, absent without credentials — are untouched.

## Impact

- `survey/assets/js/components/map_place_search.js` — the endpoint constant, the query parameters,
  and the feature-type-to-zoom table. The network call was deliberately kept in one function for
  exactly this swap; nothing outside it changes.
- `survey/assets/css/main.css` — a category line in the result row.
- Requires `collectstatic`.
- No model change, no migration, no new environment variable, no new credential.
- Billing shape changes slightly: Search Box `/forward` is billed per request, like the geocoding
  endpoint it replaces, so the existing throttles keep applying. (The `/suggest` + `/retrieve` pair
  is billed per *session* instead — see design for why we are not using it.)
- Both surfaces move together, since they share the control: respondent maps and the survey-creation
  map.
