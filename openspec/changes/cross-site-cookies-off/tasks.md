## 1. Code

- [x] 1.1 `settings.py`: `CROSS_SITE_COOKIES` from the environment only, default off
- [x] 1.2 `PartitionedCookieMiddleware`: add `Partitioned` only when the switch is on; otherwise sweep the stale partitioned `sessionid`/`csrftoken` on duplicate values in the raw Cookie header
- [x] 1.3 `render.yaml`: worker `SECRET_KEY` from `mapsurvey-shared`, comment on the manual step

## 2. Tests

- [x] 2.1 `CrossSiteCookiesTest`: the attribute test overrides `CROSS_SITE_COOKIES=True`; a default-off test
- [x] 2.2 `StalePartitionedCookieTest`: deletion on duplicates, no deletion on a single cookie, no deletion when the response sets the cookie, sessionid handled like csrftoken
- [x] 2.3 Embed tests, CSRF tests and the respondent catalog test pass

## 3. Docs

- [x] 3.1 CLAUDE.md embedding paragraph; changelog entry (`kind: fixed`)
- [ ] 3.2 PR text: the manual Render step (group `SECRET_KEY`), what stays on `CROSS_SITE_COOKIES=0`
