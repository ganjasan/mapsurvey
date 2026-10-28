## Why

An agent can build and publish a survey but cannot hand the creator what they need to send it out:
the link, a QR code for a poster, the embed snippet, campaign links. All of it is on the editor's
Share page and nowhere in the API. Block 2 of epic #408 (#410): REST first (PR 1), MCP on top (PR 2).

## What Changes

**REST (PR 1)**
- `GET /surveys/{uuid}/share` (`surveys:read`, viewer): status, `shareable`, and — when published —
  the respondent URL, the public results URL when that page is published, the embed snippet and
  the allowed embed hosts; when testing, the test link with its token (editor and up).
- `GET /surveys/{uuid}/share/qr.svg` and `qr.png?size=` (`surveys:read`): a QR code of the
  respondent URL (or of a tracked link with `link=<id>`), drawn on the server with **segno** (new
  dependency, pure Python).
- `GET/POST /surveys/{uuid}/tracked-links`, `DELETE …/tracked-links/{id}` (`surveys:read` /
  `surveys:write`, editor for writes): campaign links (UTM source, medium, campaign) with their URL
  and how many responses started and completed through each.
- `PUT /surveys/{uuid}/share/embed-hosts` (`surveys:write`, editor): the sites allowed to embed,
  through the editor's own validation.
- Request-free builders for the respondent URL and the embed snippet (`SITE_URL`), so API, MCP and
  the editor share them.
- Fixes found on the way: `TrackedLink.build_url` made `http://` links behind the proxy;
  `SurveyHeader.get_test_url` reversed a URL name that does not exist; tracked links were tied to
  whichever version row the Share page was opened on — now always the canonical survey.

**MCP (PR 2)**
- `get_share_links`, `get_qr_code` (returns the image in the chat), `list_tracked_links`,
  `create_tracked_link`, `delete_tracked_link`, `set_embed_hosts`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `rest-api-v1`: share info, QR, tracked links, embed hosts.
- `mcp-server`: distribution tools; tool results may carry an image.

## Impact

`Pipfile`/`Pipfile.lock` (segno), `survey/embedding.py` (request-free builders), `survey/models.py`
(`build_url`, `get_test_url`), `survey/share_views.py` (canonical survey), new `api/v1/share.py`,
schemas, `mcp/protocol.py` (image content), `mcp/tools/share.py`, generated references, help. No
migration.
