## MODIFIED Requirements

### Requirement: Session ids are bound to the token that initialised them
`initialize` SHALL answer with an `Mcp-Session-Id` header that is a signed value carrying the
token id, a random nonce, the issue time and the client context of the `initialize` request
(`clientInfo` name and version, trimmed, and the negotiated protocol version). A later request MAY
omit the header. A request whose `Mcp-Session-Id` fails verification or was issued to another
token SHALL be `404` with a JSON-RPC error, so the client re-initialises. A session id issued
before the client context was added SHALL keep verifying. The server SHALL store nothing per
session.

#### Scenario: Session from token A under token B
- **WHEN** token B presents the `Mcp-Session-Id` that token A's `initialize` returned
- **THEN** the response is `404` and no tool runs

#### Scenario: Tampered id
- **WHEN** a request carries an `Mcp-Session-Id` whose signature does not verify
- **THEN** the response is `404`

#### Scenario: Client context survives the stateless round trip
- **WHEN** a client initialises with `clientInfo = {name: "claude-code", version: "2.1.0"}` and later calls a tool with the returned session id
- **THEN** the tool call's analytics event names client `claude-code` version `2.1.0`

#### Scenario: Old session id
- **WHEN** a request carries a session id signed before the client context existed (token id and nonce only)
- **THEN** it verifies and the call runs

### Requirement: Observability without arguments
Every `tools/call` SHALL emit the PostHog event `mcp_tool_called` with `tool`, `outcome` (`ok` or
the error code), `token_id` and `kind`, and nothing from the arguments. Writes SHALL be audited by
the services with `surface = "mcp"`.

The server SHALL also emit the events PostHog's MCP Analytics reads:

- `$mcp_tool_call` for every `tools/call` of a registered tool, with `$mcp_tool_name`,
  `$mcp_is_error`, `$mcp_duration_ms` and, on an error, `$mcp_error_type` (`permission` for
  `scope_missing`/`forbidden_role`/`pro_required`, `rate_limited`, `validation` for
  `invalid_arguments`/`validation`/`bad_cursor`, `missing_context` for `confirmation_required`,
  `internal` for `server_error`, `api_4xx` for any other code), `$mcp_error_status` (the HTTP
  status of the envelope, when there is one) and `$mcp_error_message` (the error code);
- `$mcp_initialize` for every successful `initialize`;
- `$mcp_tools_list` for every successful `tools/list`, with `$mcp_listed_tool_names` (the names
  the token sees) and `tool_count`.

Each of them SHALL carry `$mcp_server_name`, `$mcp_server_version`, `$mcp_protocol_version`,
`$mcp_source`, `$mcp_client_name`/`$mcp_client_version` (from the session, or from `clientInfo`
on `initialize`), `$mcp_client_user_agent`, `$mcp_vendor_client` (the `x-anthropic-client`
header) and, when the request carries a session id with an issue time, `$session_id` — a UUIDv7
that is the same for every request of one session. None of them SHALL carry `$mcp_parameters`,
`$mcp_response`, `$mcp_intent`, an error `detail`, or any argument value.

#### Scenario: Event on refusal
- **WHEN** `delete_survey` is refused with `confirmation_required`
- **THEN** one `mcp_tool_called` is emitted with `tool = "delete_survey"` and `outcome = "confirmation_required"` and no survey uuid in its properties
- **AND** one `$mcp_tool_call` is emitted with `$mcp_tool_name = "delete_survey"`, `$mcp_is_error = true`, `$mcp_error_type = "missing_context"` and no survey uuid in its properties

#### Scenario: Successful call
- **WHEN** `get_survey` succeeds within a session
- **THEN** `$mcp_tool_call` has `$mcp_is_error = false`, a numeric `$mcp_duration_ms`, no `$mcp_error_type`, and the same `$session_id` as the session's other calls

#### Scenario: Validation error keeps argument values out
- **WHEN** `update_survey` is called with an unknown field whose value is a distinctive string
- **THEN** `$mcp_tool_call` has `$mcp_error_type = "validation"` and the string appears in no event property

#### Scenario: Advertised tools
- **WHEN** a read-only token calls `tools/list`
- **THEN** `$mcp_tools_list` lists exactly the names in the response and `tool_count` equals their number

#### Scenario: Harness signals
- **WHEN** a request carries `User-Agent: claude-code/2.1.0 (cli)` and `x-anthropic-client: ClaudeCode`
- **THEN** the event has `$mcp_client_user_agent = "claude-code/2.1.0 (cli)"` and `$mcp_vendor_client = "ClaudeCode"`
