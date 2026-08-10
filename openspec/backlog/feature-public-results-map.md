# Public results map showing all collected points

**Type**: feature
**Priority**: high
**Area**: frontend
**Epic**: pro-tier
**Tier**: **Pro**
**Created**: 2026-03-26
**Updated**: 2026-07-29 — assigned to the Pro tier; priority raised from medium

## Description

A public-facing map page that displays all collected geometries from a survey. Allows survey creators to share results with their community — e.g. "here are all the snowdrop sightings we've collected so far".

## Notes

- Source: Marijana Jericevic (Galanthus) — wants to show collected snowdrop locations to her community
- Also relevant for: lrbenedict12 (show all student polygon answers), Manuel Frost (show collected quiet zones)
- Related to "Results dashboard" feature but simpler — just a map with points/polygons, no stats
- URL: /surveys/<uuid>/results/ (public or unlisted)
- For live-updating (event) use, layer on [Real-time updates for public results (live delivery layer)](feature-realtime-public-results.md) (#83) — this page is the surface it updates
- **Pro tier (2026-07-29)**: this is the deliverable a consultancy hands to its client, so
  it is the cleanest paid feature in the whole product. Pairs with
  [custom domain](feature-custom-domain.md) (#89) and
  [white-label branding](feature-white-label-branding.md) (#90) — client-branded results on
  the client's own domain is the package that gets sold. See [epics/pro-tier.md](epics/pro-tier.md).
- Free users still see their own results inside the editor (counts + points on a map);
  what Pro buys is the *public, shareable, branded* surface.

## Literature support (added 2026-07-31)

The PPGIS research says this feature is not cosmetic — it is what keeps participation
rates alive over repeat projects:

- Brown & Kyttä (2014), the standard synthesis, state that PPGIS sponsors have an ethical
  obligation to be honest about whether collected data will actually influence decisions,
  and that participants disengage when their role is purely informational. Publishing
  results is the visible half of that bargain.
- Their positive counter-example is Vaasa (Finland), where PPGIS results fed an
  architectural competition and the inhabitants' viewpoints stayed visible in the final
  plan — participation used across the planning cycle rather than as a one-off intake.
- Laborgne & Klöcker (2023, Karlsruhe heat survey) name the opposite failure: the
  knowledge generated stayed disconnected from local strategy.

For a consultancy this converts into a sales argument: a published results map is the
proof-of-process artefact their municipal client can point at. Full notes:
`docs/research/ppgis-heat-participation.md`.

## Status

- **2026-08-10 — CLOSED** in PR #54. Public page at `/r/<slug>/` (`survey/urls.py:126`, `survey/views.py:1378`); map blocks emit a GeoJSON FeatureCollection (`survey/public_results.py:215-250`) rendered with Leaflet (`survey/templates/public_results.html:230-242`). k-anonymity masking and creator-selected popup fields shipped with it. Real-time updates are tracked separately as #83.
