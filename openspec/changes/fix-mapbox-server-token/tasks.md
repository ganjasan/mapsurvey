# Tasks: fix-mapbox-server-token

## 1. Code

- [x] 1.1 `MAPBOX_SERVER_TOKEN` setting in `mapsurvey/settings.py`, with a comment on why it is separate
- [x] 1.2 `fetch_basemap()` takes the server token first, the public token as fallback
- [x] 1.3 `render.yaml` declares `MAPBOX_SERVER_TOKEN` (`sync: false`); `.env.example` documents it

## 2. Tests

- [x] 2.1 Server token wins over the public token
- [x] 2.2 Public token is the fallback when the server token is empty
- [x] 2.3 No-token tests clear both settings, so a local `.env` with a server token cannot mask them

## 3. Delivery

- [x] 3.1 PR to `master`
- [ ] 3.2 After merge: set `MAPBOX_SERVER_TOKEN` on the Render web service, print a map section and check the basemap is there
