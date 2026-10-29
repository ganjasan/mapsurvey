# rest-api-v1 — delta for operator-entry

## ADDED Requirements

### Requirement: Structure schemas carry the audience
Section, group and question input and output schemas SHALL carry `audience`
(`everyone` | `respondents` | `operators`), optional on input, always present on output; the MCP
tools built over the same schemas SHALL accept and return it. The generated references
(`reference/api.md`, `reference/mcp-tools.md`) SHALL be regenerated in the same change.

#### Scenario: Set over the API
- **WHEN** a client PATCHes a question with `{"audience": "operators"}`
- **THEN** the response body has `"audience": "operators"` and the respondent page no longer shows the question

#### Scenario: Unknown value
- **WHEN** a client PATCHes `{"audience": "staff"}`
- **THEN** the response is `422 validation` naming `audience`

#### Scenario: Live survey
- **WHEN** a client PATCHes the audience on a published survey without unpublished changes
- **THEN** the response is `409 draft_required`
