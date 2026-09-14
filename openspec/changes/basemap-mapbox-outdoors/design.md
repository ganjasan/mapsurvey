## Context

Every Mapsurvey map is a Leaflet map with three selectable basemaps, stored per survey as
`SurveyHeader.basemaps` (`streets` / `satellite` / `topo`). Today the providers behind those slugs
are spread across four places:

| Surface | Template | streets | topo |
|---|---|---|---|
| Respondent, analytics map, session mini-map, section picker | `partials/basemap_layers.html` (shared) | Mapbox (`var mapboxUrl`) | OpenTopoMap, hard-coded |
| Editor create wizard | `editor/survey_create.html` | Mapbox (`{{ MAPBOX_URL }}`) | OpenTopoMap, hard-coded |
| Public results `/r/<slug>/` | `public_results.html` | **`{s}.tile.openstreetmap.org`, hard-coded** | OpenTopoMap, hard-coded |

`basemap_layers.html` is unusual: it reads `mapboxUrl` and `mapboxAccessToken` as JavaScript
variables from the enclosing scope, so each of its four including templates declares that pair of
`var`s first. Nothing else in those templates uses the variables.

The OSM Foundation has now started returning `403` blocked-tiles to some clients — a creator in
Poland saw a Response Map covered in them. We already pay for Mapbox and ship the public token
(`pk.…`) to every browser, so the volunteer dependency buys us nothing.

## Goals / Non-Goals

**Goals:**
- No Mapsurvey surface requests tiles from a volunteer-run server.
- `topo` renders Mapbox Outdoors (`mapbox/outdoors-v12`) everywhere, with one definition of the URL.
- Public results uses the same providers as every other map instead of its own hard-coded set.
- `basemaps` / `default_basemap` values keep working untouched — no migration, no creator action.

**Non-Goals:**
- Changing the set of basemap slugs, adding a provider picker, or making providers per-survey.
- Self-hosting tiles, adding a tile proxy, or caching tiles.
- Touching the Esri satellite layer, which is neither volunteer-run nor blocked.
- A `tileerror` fallback UI. With a paid provider on every layer there is no expected error state;
  adding one now would be speculative chrome.

## Decisions

**1. Mapbox Outdoors for `topo`, not a fallback chain on OpenTopoMap.**
Owner decision, taken after comparing rendered samples. Outdoors gives hillshade + labelled contour
lines, retina tiles, and zoom to 22 (OpenTopoMap stops at 17 and has no `@2x`), and it is visually
consistent with Streets, so switching layers no longer looks like switching products. OpenTopoMap's
cartography is the denser, more classic topo map — but it is served by volunteers under a policy we
cannot guarantee we satisfy, which is the whole reason this change exists. *Alternative considered:*
keep OpenTopoMap and add a `tileerror` fallback to Streets. Rejected — it keeps the violation and
degrades silently instead of removing the cause.

**2. The Outdoors URL is a setting, not a template literal.**
`MAPBOX_OUTDOORS_URL` sits next to `MAPBOX_URL` in `settings.py` with a working default
(`https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/tiles/256/{z}/{x}/{y}@2x?access_token={accessToken}`)
and is exposed by the existing `mapbox` context processor. Style versions move (`outdoors-v11` →
`v12`); a template literal would mean editing five files next time. Same reason `MAPBOX_URL` is a
setting today. *Alternative considered:* derive the Outdoors URL from `MAPBOX_URL` by string
replacement. Rejected — that silently breaks the moment someone points `MAPBOX_URL` at a custom
style, which is exactly what the env var exists for.

**3. `basemap_layers.html` reads the context directly and stops depending on enclosing `var`s.**
The partial becomes self-contained: `{{ MAPBOX_URL }}`, `{{ MAPBOX_OUTDOORS_URL }}`,
`{{ MAPBOX_ACCESS_TOKEN }}`. The four `var mapboxUrl` / `var mapboxAccessToken` declarations in the
including templates are then dead and get deleted. Otherwise each of those four templates would
need a third `var mapboxOutdoorsUrl` added in the right order — a coupling that is invisible until a
new including template forgets one and the Topo layer silently 404s. Safe because every one of those
templates is rendered through `render(request, …)`, so the context processor always runs (no
`render_to_string` call renders them).

**4. Public results switches to the same context variables rather than keeping its own table.**
The comment there claims the page is "self-contained (no Mapbox token needed on the public page)" —
that premise is wrong: the token is a public `pk.` token already served to anonymous respondents on
every survey page. Keeping a second provider table is what let this page drift into the policy
violation in the first place. The Esri satellite entry stays as-is; it is the one provider with no
settings equivalent.

**5. Attribution follows the provider.** Mapbox-served layers carry
`© Mapbox © OpenStreetMap`, which is what Mapbox's terms require. Dropping the OpenTopoMap
attribution is not optional — leaving it would credit a provider we no longer use.

## Risks / Trade-offs

- **Tile quota.** Topo and public-results traffic now bills against Mapbox → both are low-volume
  (Topo is rarely the default basemap, public results pages are few and lightly trafficked), and the
  alternative is serving creators blocked-tile mosaics. Worth watching on the Mapbox usage page after
  deploy, not worth pre-optimising.
- **Cartographic regression for topo users.** Outdoors has sparser contour lines than OpenTopoMap, so
  a creator mapping mountain terrain loses some detail → mitigated by hillshade plus zoom to 22, well
  past OpenTopoMap's 17; a survey that genuinely needs a survey-grade topo map is better served by
  the reference-overlay-layers feature (creator-supplied WMS/XYZ).
- **Token exposure on one more surface.** Public results now uses the `pk.` token → it is already
  public on every respondent page and is URL-restrictable in the Mapbox dashboard; no new class of
  exposure.
- **Merge reaches production within minutes and there is no kill switch here.** → the rollback is a
  revert, and the failure mode is cosmetic (a basemap renders in a different style), not a broken
  survey. An env-var switch for a tile URL would be ceremony around a one-line revert.

## Migration Plan

1. Ship the setting, the context processor field, and the template changes together — nothing is
   staged, since a template referencing `MAPBOX_OUTDOORS_URL` before the setting exists renders an
   empty tile URL.
2. No production env var is required: the default value is the intended production value.
   `MAPBOX_OUTDOORS_URL` may be set on Render later to pin a different style.
3. Verify after deploy: open a survey with `topo` enabled, switch the basemap, confirm Mapbox
   Outdoors tiles and `© Mapbox © OpenStreetMap` attribution; open a `/r/<slug>/` page with a map
   block and confirm it no longer requests `tile.openstreetmap.org`.
4. Rollback: revert the commit. No data is written, so there is nothing to undo.
5. Reply to the reporting creator (`dawgranat@gmail.com`) once deployed — short, per the bug-fix
   email convention.
