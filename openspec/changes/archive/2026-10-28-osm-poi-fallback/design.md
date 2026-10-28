## Context

Two geocoders with complementary strengths. Mapbox: better addresses, wide language support,
a paid SLA, and POI coverage concentrated in North America and Western Europe. Photon (OSM): POI
coverage wherever a local mapping community exists, no key, EU-hosted, no SLA, and four supported
languages (`default, de, en, fr` — anything else is an HTTP 400, not a graceful fallback).

The control already isolates the network call in one function, which is what makes a second provider
tractable. What it does not yet have is a provider-agnostic result shape: `describe()` and `select()`
read Mapbox's field names directly.

## Goals / Non-Goals

**Goals**

- A named place that OSM knows and Mapbox does not becomes findable.
- Nothing that works today regresses, including when the fallback is down.
- One result shape, two adapters, so a provider can be swapped or added without touching the UI.
- ODbL attribution wherever OSM data is shown.

**Non-Goals**

- Replacing Mapbox. Addresses and languages are its job.
- Self-hosting Photon.
- Using OSM for addresses, reverse geocoding, or category browsing.
- Merging *ranking* across providers — we append, we do not interleave by score.

## Decisions

### Trigger: the primary provider did not answer the query

First implementation triggered on "the response contains no `feature_type === 'poi'`". Measured in
Belo Horizonte, that is not enough: "Mercado Central BH" comes back as five holiday rentals *named
after the market* — "Apto Dallas I Raul Soares Centro Mercado Central BH". Those are POIs by type
and useless by content, so the fallback never fired on one of the cases that motivated it.

The trigger is therefore: **no result's name starts with the query's first word.**

| query | primary's best | starts with lead word? | fallback |
|---|---|---|---|
| Sportschwimmhalle Jena | Sportschwimmhalle Schwimmparadies | yes | not consulted |
| Wagnergasse 25 Jena | Wagnergasse 25 | yes | not consulted |
| Bishkek | Bishkek | yes | not consulted |
| Ошский рынок | Markt | no | consulted |
| ЦУМ Бишкек | Bishkek | no | consulted |
| Mercado Central BH | Apto Dallas I … | no | consulted |
| 東京都庁 | 東 | no | consulted |

Leading-word rather than substring matters: the rentals contain every word of "Mercado Central BH"
further along their names, and a substring test would have called that an answer.

This also makes the fallback cheap where it is not needed. In Jena and for address queries the
second request is never issued at all — measured, `osm:нет` on every European case tested.

### Only real places come back from the fallback

Photon answers "Bishkek" with `place:city` — the same thing Mapbox already returned, so taking it
would duplicate the list with a worse-labelled row. The fallback therefore keeps only features whose
`osm_key` is outside `place` and `boundary`, and which carry a `name`.

That admits parks, markets, halls, stations, shops, town halls; it rejects cities, districts,
suburbs, countries and admin polygons. Addresses without a name are rejected by the same rule.

### Merged, not interleaved: OSM POIs first, then the primary results

The fallback only runs when the primary provider did not answer, so its results are the ones the
respondent is most likely after: they go first, and the Mapbox rows follow intact and in their
original order. At most three OSM rows are added, so the list stays scannable.

An earlier version ran the fallback more eagerly and put OSM first unconditionally, which put bus
stops and a nightclub named "Bishkek" above the city of Bishkek. Tying the trigger and the ordering
to the same question — did the primary answer? — removes that case entirely.

We do not attempt cross-provider relevance scoring. Two providers' scores are not comparable, and
inventing a blend would be a source of confident nonsense.

### Deduplication by position

A feature whose coordinates round to the same 3 decimal places (~100m) as an existing result is
dropped. Name comparison is not used: the two providers spell the same place differently
("Estação São Gabriel" vs "Estação São Gabriel - Setor Oeste"), and position is the thing we
actually care about — two rows that fly the map to the same spot are a bug regardless of naming.

### Photon's `extent` is not a GeoJSON bbox

Measured: Bishkek comes back as `[74.4548909, 43.0125007, 74.7177168, 42.7155529]` — that is
`[west, north, east, south]`, while GeoJSON `bbox` (and Mapbox) is `[west, south, east, north]`.
The adapter converts to Leaflet's `[[south, west], [north, east]]` explicitly. Feeding the raw array
to `fitBounds` would silently produce a mirrored viewport.

### Language: send it only when supported

`PHOTON_LANGS = ['de', 'en', 'fr']`. Anything else — Portuguese for our Belo Horizonte user, Russian,
Japanese — is omitted, and Photon answers in its `default` (local names). That is the right
behaviour anyway: a respondent in Bishkek searching in Russian wants "Ошский рынок", not a
transliteration.

Never pass an unsupported code through: it is an HTTP 400, which would turn the fail-open path into
the only path.

### Sequential, with a timeout, before rendering

The fallback runs after the primary response, and only when triggered; the list renders once, with
both sets already merged. The alternative — render Mapbox rows immediately and inject OSM rows a
moment later — moves the list under the respondent's cursor or keyboard selection, which is worse
than waiting.

The wait is bounded at 1.5s — measured responses are 200–400ms. The bound is a `Promise.race`
against a timer, not only an `AbortController`: aborting assumes the transport honours the signal,
whereas racing guarantees the list renders on time whatever the network layer does. (Found by
testing with a fetch that never settles: the abort-only version hung indefinitely.) The abort still
fires, to stop the request.

On timeout, error, or empty result the merge is skipped and the primary results render as they do
today. No error message: from the respondent's point of view nothing failed, they simply got the
same list as before. Worst case end-to-end with a dead fallback, measured: ~2.2s from keystroke to
list.

### Attribution

A footer row on the result list, shown only when the list contains OSM-derived results:
"© OpenStreetMap contributors", linking to the copyright page. Per-row source badges were considered
and dropped — they push the useful text sideways for a legal requirement a footer satisfies.

## Risks / Trade-offs

- **A dependency with no SLA.** Photon's public instance can disappear without notice. The fail-open
  path means that degrades the search back to today's behaviour rather than breaking it, and nothing
  in the respondent's flow blocks on it beyond 1.5s. Escalation, if it ever matters: self-host.
- **Extra requests.** A query the primary provider does not answer costs a second request. Queries
  it does answer — most European and US ones, and all address lookups tested — cost nothing extra.
  Photon's public instance asks for reasonable use rather than a hard quota; our throttles (3-char
  floor, 300ms debounce, per-page cache) apply to both providers because they sit above the merge.
- **Two data licences in one list.** Mapbox terms and ODbL side by side. The attribution row is the
  mitigation; nothing is stored from either provider, which keeps us clear of the share-alike
  obligations that attach to derived databases.
- **Mixed naming conventions.** OSM rows can read oddly next to Mapbox rows ("Торговый центр «Кыял»
  Ошский рынок"). The location is right, which is what the search is for.
- **A correct answer whose name does not lead with the query's first word triggers the fallback.**
  "Klinikum Jena" resolves to "Universitätsklinikum Jena", which does not start with "klinikum", so
  OSM is consulted and its rows go on top. Both providers return the same hospital there, so the
  cost is a request and a redundant row rather than a wrong answer.
- **Photon's naming follows the browser's `Accept-Language` when we send no `lang`.** Measured: the
  same query returns "Торговый центр «Кыял» Ошский рынок" from curl and "Oshskiy Rynok Torgoviy
  Center Kyal" from an `en-US` browser. Since we only send `lang` for de/en/fr, respondents in other
  languages get names shaped by their own browser preference — usually what they want, but it is the
  browser deciding, not us.

## Migration Plan

Client-side only. `collectstatic`, deploy, done. No state, no backfill. Rollback is removing the
fallback call; the adapters are additive.

## Open Questions

- If Photon proves reliable and useful, does it become primary for POI everywhere rather than a
  fallback? That needs the wider measurement (~100 queries across our six regions) we deferred, and
  it needs the language gap solved — which realistically means self-hosting with a fuller index.
