# Proposal: fix-mapbox-server-token

## Why

Issue [#518](https://github.com/ganjasan/mapsurvey/issues/518). Mapsurvey moved to its own Mapbox
account on 2026-11-02, and the production `MAPBOX_ACCESS_TOKEN` is now URL-restricted to
`https://mapsurvey.org`. That token ships to every respondent's browser, so the restriction is what
keeps other sites from spending our tile quota.

The printable form calls the Mapbox Static Images API from the server with the same token
(`survey/print/static_map.py`). A server request carries no `Referer`, so Mapbox answers 403 and
every printed map falls back to the "Map unavailable" frame. Reproduced: Static Images request with
the production token and no Referer → 403.

A URL restriction cannot allow a request without a Referer, so the browser token and the server
token have to be two tokens.

## What Changes

- New setting `MAPBOX_SERVER_TOKEN` (env var of the same name): a token used only for server-side
  Mapbox calls and never rendered into a page. It may be unrestricted.
- `fetch_basemap()` uses `MAPBOX_SERVER_TOKEN`, falling back to `MAPBOX_ACCESS_TOKEN` when it is
  empty — local dev and deployments with an unrestricted public token keep working unchanged.
- `render.yaml` declares `MAPBOX_SERVER_TOKEN` (`sync: false`); `.env.example` documents both tokens.
- Not touched: the `mapbox` context processor still exposes only `MAPBOX_ACCESS_TOKEN`;
  `scripts/report_tools/maplib.py` is a local tool run with the dev token.

## Impact

- `mapsurvey/settings.py`, `survey/print/static_map.py`, `render.yaml`, `.env.example`.
- `survey/tests/test_printable_form.py` — token precedence; no-token tests clear both settings.
- Ops: set `MAPBOX_SERVER_TOKEN` on the Render web service after merge (no redeploy needed beyond
  the env change).
