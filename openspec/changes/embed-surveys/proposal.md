## Why

Creators keep asking to put a Mapsurvey survey *inside* their own site — a municipality's
project page, a consultant's client portal, a research group's site on Tilda, Webflow, Wix,
Squarespace, Notion or WordPress — instead of sending respondents away to a link. Today that
is impossible: the site-wide `X_FRAME_OPTIONS = 'SAMEORIGIN'` makes any third-party `<iframe>`
render empty, and even without that header the respondent flow would break, because every
piece of respondent state (`survey_session_id`, language, password gate, test access, UTM
params) lives in the Django session cookie, which carries the default `SameSite=Lax` and is
therefore not sent inside a cross-site frame. The Share page already promises the feature in
spirit — the `embed_copied` product event is declared in `creator-distribution-events` and
`product_events.py` — but no control emits it. GitHub issue #284.

## What Changes

**Phase 1 — iframe embed**

- Respondent-facing responses (`/surveys/<slug>/…`: entry, language picker, password gate,
  sections, uploads, layer GeoJSON and objects, thanks page, closed/unavailable pages) drop
  `X-Frame-Options` and instead carry `Content-Security-Policy: frame-ancestors …` built from a
  per-survey **allowed-hosts list**. Empty list (the default) = any site may embed. The
  decision is made where `check_survey_access` already marks indexing; a middleware applies
  the header, mirroring `SurveyIndexingMiddleware`.
- New `SurveyHeader.embed_allowed_hosts` (list of hostnames, `*.` wildcard allowed) edited on
  the Share page. Mapsurvey's own origin is always allowed so the editor's Live Preview keeps
  working.
- Session and CSRF cookies become `SameSite=None; Secure; Partitioned` when the site runs over
  HTTPS (production and Render previews). Django 4.2 has no `Partitioned` setting, so a small
  middleware appends the attribute to those two `Set-Cookie` headers. Local HTTP development
  keeps `Lax`.
- The Share page gains an **Embed** section: the iframe snippet (with
  `allow="geolocation; fullscreen"`, which an iframe needs before the respondent map may ask
  for the device location), a copy button that emits `embed_copied`, the allowed-hosts form,
  and a one-line explanation of what the badge and Pro mean for embeds.
- A tiny `embed.js` the snippet loads from Mapsurvey: the respondent page posts its content
  height to the parent via `postMessage`; the script resizes the matching iframe. Map-layout
  sections keep the snippet's height; form-layout sections grow with their content.
- Embedded sessions are recognisable: `session_start` metadata gains `embedded: true` and
  `embed_host` (the embedding page's host, from the Referer of the frame load), so
  Responses → Traffic Sources can tell embed traffic from link traffic.
- When the respondent is inside a frame, finishing the survey never navigates the frame to a
  foreign site: a survey with a custom `redirect_url` renders the built-in thanks page inside
  the frame with a "Continue" link that opens the redirect in the top window.
- Free for every tier. The "Made with Mapsurvey" badge stays inside the embed exactly as on
  the survey page; Pro's `show_branding` already removes it.

**Phase 2 — other platforms (oEmbed)**

- New endpoint `GET /oembed/?url=<survey url>&format=json[&maxwidth&maxheight]` returning an
  oEmbed `rich` payload whose `html` is the same iframe snippet. Only a published,
  embeddable survey URL resolves; everything else is 404. `format=xml` returns 501.
- The respondent entry page advertises it with
  `<link rel="alternate" type="application/json+oembed" …>` so platforms that do oEmbed
  discovery (Notion, Medium, WordPress for users who may embed arbitrary URLs, Ghost, …)
  turn a pasted survey link into the embedded survey.

Not in scope: embedding the public results page `/r/<slug>/`; a WordPress plugin; per-embed
analytics beyond the host; Safari-specific workarounds (Safari's third-party-cookie handling
is verified in e2e on a real device as part of this change, and a signed-token fallback is
recorded as a follow-up if it fails).

## Capabilities

### New Capabilities
- `survey-embedding`: framing policy for respondent pages (`frame-ancestors` from the
  per-survey allow-list, X-Frame-Options exemption), cross-site cookie attributes, the Share
  page Embed section and snippet, `embed.js` auto-height, embedded-session metadata, and
  completion behaviour inside a frame.
- `survey-oembed`: the oEmbed endpoint and discovery link.

### Modified Capabilities
- `creator-distribution-events`: the "copies the embed snippet (`embed_copied`)" clause gets
  its scenario — the event is captured from the Share page's embed copy button with
  `surface: 'share_page'`.
- `survey-thanks-page`: "Custom redirect URL takes precedence" gains an exception — inside a
  frame the built-in thanks page is served with a top-window "Continue" link instead of
  redirecting the frame.

## Impact

- **Settings**: `X_FRAME_OPTIONS` stays `SAMEORIGIN` for everything that is not a respondent
  page (editor, landing, admin). `SESSION_COOKIE_SAMESITE`, `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SAMESITE`, `CSRF_COOKIE_SECURE` become environment-dependent. Django's CSRF
  middleware still rejects cross-site POSTs via its Origin/Referer check, so relaxing
  `SameSite` does not weaken CSRF protection for creators.
- **Model/migration**: one new JSONField on `SurveyHeader` (`embed_allowed_hosts`, default
  `[]`), exported/imported by `serialization.py` like other header settings.
- **Code**: `survey/access_control.py` (mark embeddable), `survey/middleware.py` (two new
  middlewares), `survey/share_views.py` + `editor/survey_share.html` (Embed section, allowed
  hosts form), `survey/views.py` (`survey_thanks`, final-section completion, oEmbed view,
  discovery link context), `survey/events.py` (`session_start` metadata),
  `base_survey_template.html` (height postMessage, discovery link), new static `embed.js`,
  `survey/urls.py`.
- **Tests**: unit tests in `survey/tests.py` for headers, cookies, allow-list parsing, oEmbed,
  thanks-in-frame, session metadata; one Playwright e2e in `tests_e2e/` that embeds a
  published survey in a page served from a second origin and completes it (the real check that
  cookies survive inside a frame).
- **Docs**: Share page copy explains embedding; `legal/` cookie wording unchanged (same two
  first-party cookies, no new data collected).
