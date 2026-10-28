## ADDED Requirements

### Requirement: Distribution tools
The MCP server SHALL offer `get_share_links`, `get_qr_code`, `list_tracked_links` under
`surveys:read`, and `create_tracked_link`, `delete_tracked_link`, `set_embed_hosts` under
`surveys:write`, each over the REST functions of the same name. `get_qr_code` SHALL return the QR
as a PNG image content block next to the `{note, data}` text block, `data` carrying the encoded URL
(the REST SVG route needs a bearer, so it is no use to the person and is not handed over).

#### Scenario: QR in the chat
- **WHEN** an agent calls `get_qr_code` for a published survey
- **THEN** the result's `content` holds a text block and an `image/png` block, and `structuredContent.data.url` is the respondent URL

#### Scenario: Tracked link from a chat
- **WHEN** an agent with `surveys:write` calls `create_tracked_link` with `utm_source: "newsletter"`
- **THEN** the result carries the new link's URL with `utm_source=newsletter`
