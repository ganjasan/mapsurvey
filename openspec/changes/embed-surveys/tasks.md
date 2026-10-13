## 1. Data model and settings

- [x] 1.1 Add `SurveyHeader.embed_allowed_hosts = JSONField(default=list)` with help text; migration
- [x] 1.2 `survey/embedding.py`: `normalise_allowed_hosts(text) -> list` (lower-case, strip scheme/port/path, `*.` wildcard, IDNA, dedupe, raise on invalid) and `frame_ancestors(hosts) -> str`
- [x] 1.3 Export/import `embed_allowed_hosts` in `serialization.py` (default `[]`)
- [x] 1.4 `settings.py`: `CROSS_SITE_COOKIES` switch (default `not DEBUG`) driving `SESSION_COOKIE_SAMESITE/SECURE` and `CSRF_COOKIE_SAMESITE/SECURE`; documented in the settings comment and in `run_e2e.sh` (the dev server is started separately with `CROSS_SITE_COOKIES=1`)

## 2. Framing and cookies

- [x] 2.1 `access_control.mark_embeddable(request, survey)` called from `check_survey_access` (before any early return that renders a page for a resolved survey, after the draft 404)
- [x] 2.2 `SurveyEmbedMiddleware`: set `Content-Security-Policy: frame-ancestors …`, drop `X-Frame-Options` when the request is marked; register after `XFrameOptionsMiddleware`
- [x] 2.3 `PartitionedCookieMiddleware`: append `; Partitioned` to `Set-Cookie` for the session and CSRF cookie names when `Secure`; register outermost
- [x] 2.4 Unit tests: frame-ancestors on entry/section/closed/thanks, SAMEORIGIN on editor/landing/draft-404, allow-list rendering, cookie attributes on/off via `override_settings`, CSRF Origin rejection

## 3. Respondent page: embed signals, height, completion

- [x] 3.1 `survey/embedding.py`: `is_framed(request)` (Sec-Fetch-Dest/Site or `embed=1`) and `embed_host(request)`; extend `build_session_start_metadata` with `embedded` and `embed_host`
- [x] 3.2 `base_survey_template.html`: when framed, send `MS-Embedded: 1` on HTMX requests (`htmx:configRequest`) and post height messages on load, `htmx:afterSwap` and `ResizeObserver`
- [x] 3.3 Final-section completion: when `MS-Embedded: 1` and `redirect_url` is a valid URL, redirect to the thanks page with `next=`; `survey_thanks` validates `next` against the survey's cleaned `redirect_url` and renders the "Continue" `target="_top"` link (thanks template)
- [x] 3.4 Unit tests: session_start metadata (cross-site frame, top-level, same-origin preview), framed completion redirect, thanks `next` accepted/forged, top-level unchanged

## 4. Share page and embed.js

- [x] 4.1 `survey/assets/embed.js` (height listener, source check) and exclude it from manifest hashing so `/staticfiles/embed.js` stays stable; test that it is served
- [x] 4.2 `share_views.py`: `EmbedHostsForm`, `embed_settings` POST endpoint writing to `canonical_of(survey)`, snippet string builder shared with oEmbed (`embedding.snippet_html(request, survey, width, height)`)
- [x] 4.3 `survey_share.html`: Embed section (snippet textarea, copy button → `trackShare('embed_copied')`, allowed-hosts form, badge/Pro note), only when `is_shareable`
- [x] 4.4 `urls.py` route for the embed settings POST
- [x] 4.5 Unit tests: snippet present/withheld, hosts normalised and saved on canonical, invalid host error, draft-copy writes to canonical, export/import round-trip

## 5. oEmbed

- [x] 5.1 `views.oembed`: parse `url`, resolve survey, anonymous access check (published, not held, no password), JSON payload, `maxwidth/maxheight` clamp, CORS header, 404/501 paths
- [x] 5.2 Discovery `<link>` in `base_survey_template.html` head when the survey is anonymously openable (context from the section/entry views)
- [x] 5.3 `urls.py` route `/oembed/`; exclude it from PostHog page tracking prefixes if needed
- [x] 5.4 Unit tests: resolves, max dimensions, unpublished/foreign/xml refusals, discovery link present/absent

## 6. End-to-end and docs

- [x] 6.1 `tests_e2e/test_embed.py`: a throwaway loopback HTTP server hosts a page with the snippet pointing at the dev server (started with `CROSS_SITE_COOKIES=1`); completes a two-section survey inside the frame; asserts one session with both answers, the thanks page with the top-window Continue link in the frame, and the auto-resized frame. Passes in Chromium; WebKit skips locally (no Secure cookies over plain http) — verify Safari on the HTTPS Render preview
- [x] 6.2 Share page copy reviewed (what the badge means in an embed, map height note); `CLAUDE.md` architecture note on `survey/embedding.py` and the two middlewares
- [x] 6.3 Run `./run_tests.sh survey` baseline and after; run the e2e; summarise
