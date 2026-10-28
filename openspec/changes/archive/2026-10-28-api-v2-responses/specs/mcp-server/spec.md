## ADDED Requirements

### Requirement: Response tools
The MCP server SHALL offer `get_response_summary`, `list_responses`, `list_text_answers`,
`get_answer_geojson` and `get_export_link` under scope `responses:read`, and `moderate_response`
under `responses:moderate`, each calling the same functions as the REST routes of the same name and
taking the same parameters plus ids. Every result SHALL be wrapped in `{note, data}` with respondent
text inside `data`. `tools/list` SHALL omit tools the token's scopes lack. `moderate_response` SHALL
NOT require `confirm` (it can be changed back). The help page SHALL no longer say that the server
does not read responses, and the tool reference SHALL be regenerated.

#### Scenario: Report from a chat
- **WHEN** an agent with `responses:read` calls `get_response_summary` on a survey with answers
- **THEN** the result's `data` holds the per-question statistics the REST summary returns for the same parameters

#### Scenario: Export link in a chat
- **WHEN** the agent calls `get_export_link` with `format: "xlsx"`
- **THEN** it receives a URL that downloads the workbook for 15 minutes

#### Scenario: Moderation needs its scope
- **WHEN** a token without `responses:moderate` lists tools
- **THEN** `moderate_response` is not listed
