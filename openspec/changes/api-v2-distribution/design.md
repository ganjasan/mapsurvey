## Context

- Share page: `survey/share_views.py` (`share_page`, `share_link_delete`, `embed_settings`, all
  `editor` role), `editor/survey_share.html`. Respondent URL = `public_base_url(request)` +
  `/surveys/<uuid>/`; embed snippet = `embedding.snippet_html(request, survey)`; allowed hosts =
  `normalise_allowed_hosts` on the canonical survey; QR drawn in the browser (qrcodejs).
- `TrackedLink(survey, utm_source*, utm_medium, utm_campaign, created_at)` — stored UTM values;
  no redirect, no click counter. Attribution: `session_start` `SurveyEvent` metadata;
  `PerformanceAnalyticsService.get_campaign_breakdown()` groups by the UTM triple into
  `{started, completed, rate}`.
- Everything that builds an absolute URL needs a request; the API already uses `SITE_URL`
  (`api/v1/out.py`).

## Goals / Non-Goals

**Goals:** an agent can hand over every way to distribute a survey, including a QR image in the
chat, and manage campaign links; the editor and the API build the same URLs.
**Non-Goals:** short links; click counting; changing the Share page's look (it keeps qrcodejs);
publishing (already a tool).

## Decisions

### D1 · Request-free URL builders
`embedding.survey_url_for(survey)` = `SITE_URL` + `reverse('survey', uuid)` and
`snippet_html(..., base=None)`: with a `base` the request is not needed. The API passes
`settings.SITE_URL`; the editor keeps `public_base_url(request)` (it serves previews on their own
host). `TrackedLink.build_url(base=None)` takes the same base; the editor passes
`public_base_url(request)` — fixing the `http://` behind the proxy.

### D2 · Share info follows the editor's gate
`shareable = status == 'published'`. Published: `url`, `embed` (`snippet` without the script for
oEmbed-style use is not needed — the Share page's snippet with the script), `embed_hosts`,
`results_url` when the public results page is published. Testing: `test_url` with `?token=` for
editor and up only (a viewer must not leak it). Draft/closed: urls null, `reason` in creator words.

### D3 · QR with segno
`GET …/share/qr.svg|qr.png` (`size` 1–40 px per module, default 10, border 4, error correction
`M`). `link=<tracked link id>` encodes that link instead. Not shareable → `409 not_shareable`.
`Cache-Control: private, max-age=300`. MCP returns the PNG as image content plus the URL in data.

### D4 · Tracked links on the canonical survey
API and editor both use `canonical_of(survey)` (the Share page could be opened on a draft row).
Create: `utm_source` required, each ≤100 chars, stripped; at most 200 links per survey
(`409 limit_reached`); editor role, `surveys:write`; audited `tracked_link_create|delete`. Counts
come from `get_campaign_breakdown()` matched on the triple (a link with no responses shows 0/0).

### D5 · Embed hosts
`PUT …/share/embed-hosts {hosts: [..]}` runs `normalise_allowed_hosts` (`InvalidHost` → 400 naming
the entry; >50 → 400); saved on the canonical survey; `[]` = any site; audited.

### D6 · MCP image content
`ok_result` accepts an optional list of images: `mcp.tools.registry.WithImages(payload, images)`;
the result's `content` gets `{"type": "image", "data": <base64>, "mimeType": "image/png"}` after the
text block. `structuredContent` stays the `{note, data}` JSON.

## Risks / Trade-offs

- [New dependency] → segno is pure Python with no dependencies; locked to 1.6.6.
- [Test link leaking through an agent] → only for editor+ and only in testing status; the token is
  the same one the editor shows.
