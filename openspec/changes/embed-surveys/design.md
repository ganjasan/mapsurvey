## Context

Respondent pages are served under `/surveys/<slug>/…` by views that all go through
`resolve_survey` + `check_survey_access`. Respondent state is the Django session cookie
(`survey_session_id`, `survey_language`, `survey_password_<id>`, `test_access_<id>`,
`utm_params`) and every section submit is an HTMX POST protected by Django CSRF. Two
site-wide settings currently make embedding impossible: `X_FRAME_OPTIONS = 'SAMEORIGIN'`
(applied by `XFrameOptionsMiddleware`) and the default `SameSite=Lax` on the session and
CSRF cookies, which browsers do not send for requests made from inside a cross-site frame.

Two existing patterns are reused: the *decide in access control, apply in middleware* split of
`mark_indexing` / `SurveyIndexingMiddleware`, and the Share page's `trackShare()` for creator
distribution events. The Live Preview in the editor frames the respondent page same-origin and
must keep working.

Stakeholders: creators (want the snippet and a predictable embed), respondents (must not notice
they are inside a frame), abuse review (a lure site could frame a Mapsurvey survey — the
per-survey allow-list and the abuse footer inside the frame are the controls).

## Goals / Non-Goals

**Goals:**
- A published survey can be framed by a third-party page and completed there, in Chrome,
  Firefox and Safari, with answers landing in one session.
- Creators get a copy-paste snippet and can restrict which hosts may frame their survey.
- Embedded traffic is distinguishable in Responses.
- Platforms that do oEmbed discovery embed the survey from a pasted link.
- No change for creators who never embed: same cookies, same editor, same badge rules.

**Non-Goals:**
- Embedding the public results page, stories or the landing.
- A WordPress plugin or per-platform snippets (the iframe works everywhere raw HTML is
  accepted; oEmbed covers the rest).
- Styling the embed to match the host page beyond the existing accent colour.
- A cookie-less respondent flow. If Safari turns out to drop partitioned cookies, a signed
  session token is a follow-up change, not part of this one.

## Decisions

### D1. Framing policy: CSP `frame-ancestors` from a per-survey allow-list, decided in access control

`check_survey_access` is the one place every respondent view passes through, and it already
decides indexing there. It gains `mark_embeddable(request, survey)` which stores the list of
allowed ancestors on the request; a new `SurveyEmbedMiddleware` (next to
`SurveyIndexingMiddleware`) sets `Content-Security-Policy: frame-ancestors …` and deletes
`X-Frame-Options` on the response. Responses without the mark keep `SAMEORIGIN`, so the
editor, landing and admin are untouched. 404 responses raised *before* the mark (unknown UUID,
drafts) stay unframeable, which is fine: there is nothing to embed.

The header value: `'self'` always (Live Preview) plus each allowed host as `https://host`
and, for `*.example.org`, `https://*.example.org`. Empty list → `frame-ancestors *`.
`http://` ancestors are not emitted: a page served over HTTP cannot frame a page whose
cookies are `Secure`-only anyway.

*Alternative rejected*: `@xframe_options_exempt` on each view + a decorator. Misses redirects
and the closed/password pages, and every new respondent view would have to remember it — the
same failure mode the indexing middleware comment warns about.

*Alternative rejected*: a global `frame-ancestors *` for `/surveys/`. Loses the creator's
ability to pin their survey to their own site, which is the one anti-phishing lever embedding
adds.

### D2. Cross-site cookies: `SameSite=None; Secure; Partitioned`, appended by middleware

Django 4.2 exposes `SESSION_COOKIE_SAMESITE`/`SECURE` and `CSRF_COOKIE_SAMESITE`/`SECURE` but
has no `Partitioned` knob. A `PartitionedCookieMiddleware` rewrites the `Set-Cookie` headers
for exactly those two cookie names, appending `; Partitioned` when the cookie is `Secure`.
Partitioned (CHIPS) is what keeps the cookie usable in Chrome once third-party cookies are
blocked and in Firefox's Total Cookie Protection; Safari 18.4+ honours it too, and ignoring it
is harmless.

All four settings are driven by one switch, `CROSS_SITE_COOKIES`, defaulting to `not DEBUG`.
Production and Render previews run over HTTPS, so they get `None; Secure`. Local HTTP
development keeps `Lax` unless the switch is set, because a `Secure` cookie on an arbitrary
HTTP host is dropped by the browser; `run_e2e.sh` sets the switch on, since Chromium and
Firefox accept `Secure` cookies from `http://localhost`.

Security review of relaxing `SameSite`: Django's `CsrfViewMiddleware` checks `Origin` (and
`Referer` on HTTPS) on every unsafe request independently of cookie attributes, so a
cross-site POST is still rejected; the CSRF token must additionally match. Clickjacking of the
editor remains blocked by `SAMEORIGIN`. Partitioning means a creator who is logged in at the
top level is anonymous inside an embedded survey on another site — that is the correct
outcome (they should see what respondents see).

*Alternative rejected*: a separate respondent cookie / signed token carried by HTMX. Touches
every respondent view, duplicates Django's session machinery, and the e2e test will tell us
whether it is needed before we pay for it.

### D3. Detecting "inside a frame" from request headers, not a URL flag

`is_framed(request)` = `Sec-Fetch-Dest == 'iframe'` and `Sec-Fetch-Site != 'same-origin'`
(the Live Preview is same-origin). All evergreen browsers send both headers. A `?embed=1`
query on the snippet URL is accepted as a secondary signal for the entry request only — it is
what the oEmbed snippet and the share snippet carry, and it survives browsers that do not send
Fetch Metadata. The flag is not stored in the session: `session_start` is emitted on the entry
request, which is the frame navigation itself, so the headers are there when they are needed.

The thanks page is a frame navigation too (HTMX issues `HX-Redirect`, the frame follows it),
so `survey_thanks` sees `Sec-Fetch-Dest: iframe` and can apply the in-frame completion rule.
The HTMX POST itself is a `fetch` (`Sec-Fetch-Dest: empty`), so the completion rule is applied
by the thanks view, not by the section view: the section view keeps redirecting to
`completion_url(survey)` unchanged, except that when the request is an HTMX call from a
framed document (the page tells us via a `MS-Embedded: 1` request header set by the embed
script in the page) the redirect goes to the thanks page, whose "Continue" link carries the
real `redirect_url` with `target="_top"`. Navigating the frame to a foreign site is never
done: most sites refuse to be framed and the respondent would see a blank box.

### D4. Embedded-session metadata

`build_session_start_metadata` gains `embedded` (bool) and `embed_host` (the Referer host of
the frame load, lower-cased, `www.` stripped — the same normalisation `_classify_referrer`
applies). `referrer_type` is unchanged: the host page is still the referrer. Responses →
Traffic Sources therefore already lists the embedding host; the new keys let a later change
filter by embed without re-deriving it.

### D5. Snippet, `embed.js` and auto-height

Snippet (one line the creator copies):

```html
<iframe src="https://<host>/surveys/<uuid>/?embed=1" style="width:100%;height:720px;border:0;"
        allow="geolocation; fullscreen" loading="lazy" title="<survey name>"></iframe>
<script async src="https://<host>/embed.js"></script>
```

`allow="geolocation"` is required: without it the respondent map's "my location" silently
fails inside a frame. `embed.js` listens for `message` events of shape
`{mapsurvey: 'height', height: <px>}` and sets the height of the iframe whose
`contentWindow` is the event source; it ignores every other origin and shape. The respondent
base template posts its `document.documentElement.scrollHeight` on load, after each HTMX
swap and from a `ResizeObserver`, only when `window.parent !== window`. Map-layout sections
fill the frame, so their reported height equals the current frame height and nothing moves;
form-layout sections grow and shrink with content. `embed.js` lives with the other assets
(`survey/assets/js/embed.js`) but is served by a tiny view at `/embed.js`: the manifest
storage hashes every collected filename, and a pasted snippet must keep working across
deploys, so the stable path cannot be a static URL.

### D6. Allowed hosts: data and UI

`SurveyHeader.embed_allowed_hosts = JSONField(default=list)`, stored on the canonical row
(`canonical_of(survey)`) because that is what `resolve_survey` serves. Input is a textarea,
one host per line; the form lower-cases, strips scheme/path/port, de-duplicates, and accepts
`hostname` or `*.hostname` (IDNA-encoded). Edited on the Share page, which is `editor`-role —
the same role that already sees the link, QR and tracking links. Exported/imported in
`serialization.py` alongside `show_branding`, defaulting to `[]` for old archives.

### D7. oEmbed

`GET /oembed/` with `url` (required), `format` (default `json`; `xml` → 501), `maxwidth`,
`maxheight`. The URL must resolve to a survey entry URL on this host (`/surveys/<uuid>/`,
query string ignored) for a survey that passes the anonymous access check (published, not
held, no password); otherwise 404. Response: `type: "rich"`, `version: "1.0"`, `title`,
`provider_name: "Mapsurvey"`, `provider_url`, `html` (the same snippet, width/height clamped
to the max params, default 720 px), `width`, `height`, `cache_age: 3600`. CORS `*` on the
endpoint, because some platforms fetch oEmbed from the browser. The survey entry page emits
`<link rel="alternate" type="application/json+oembed" href="…/oembed/?url=…&format=json"
title="…">` so discovery works. Hosts in the allow-list still apply at frame time — oEmbed
only hands out the snippet.

## Risks / Trade-offs

- [Safari drops the partitioned cookie inside a frame] → the e2e passes in Chromium against the
  HTTP dev server. WebKit refuses a `Secure` cookie from plain `http://localhost` even at top
  level (verified 2026-10-13), so the WebKit run skips locally; Safari is checked on the HTTPS
  Render preview before merge. If it fails there, the respondent sees the "start again" entry
  page on the second section rather than a 500 (`respondent-session-routing` already guarantees
  that), and a signed-token follow-up is opened.
- [`SameSite=None` applies to creators too] → CSRF stays Origin-checked; editor stays
  `SAMEORIGIN`; no new cookie is introduced.
- [A phishing page frames a legitimate survey to lend itself credibility] → the abuse footer
  ("Never enter passwords…", "Report this survey") is inside the frame; creators can pin
  hosts; abuse review can set an allow-list on a held survey.
- [Snippet height is a guess] → auto-height fixes form layouts; map layouts are documented as
  "set the height you want".
- [`embed.js` path must never change] → unhashed static path, covered by a test that fetches
  it through WhiteNoise.
- [oEmbed discovery leaks nothing new] → the endpoint returns only what the public entry page
  already shows (title) and 404s for anything not openable anonymously.

## Migration Plan

1. Migration adds `embed_allowed_hosts` with default `[]`; no data backfill.
2. Settings switch `CROSS_SITE_COOKIES` ships defaulting to `not DEBUG`: on deploy every
   creator's next response re-sets `sessionid`/`csrftoken` with the new attributes;
   sessions are not invalidated (same key, same value).
3. Rollback: revert the deploy; cookies fall back to `Lax` on the next response, the
   middleware stops emitting CSP, the column stays (harmless).

## Open Questions

- None blocking. Whether to also offer a "button that opens the survey in a modal" snippet
  is left for creator feedback after launch.
