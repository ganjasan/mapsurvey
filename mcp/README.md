# `mcp/` — the MCP server

Change `mcp-server` (#306), item 4 of epic #378: the **second resource server** of the API platform,
after REST API v1 (`api/v1/`). It speaks the Model Context Protocol over Streamable HTTP at
`settings.MCP_RESOURCE_URL` (`https://mapsurvey.org/mcp`, served by this process) and carries no
security logic of its own: `api.auth.authenticate(request, 'mcp')`, `api.rights`, `api.gates`,
`api.limits`, and every write through `survey/services/` with `Actor(surface='mcp')`.

## What is where

| Module | Holds |
|---|---|
| `views.py` | `endpoint` (Origin → bearer → method → version header → body → session → dispatch) and the RFC 9728 document `protected_resource_metadata`. |
| `protocol.py` | The JSON-RPC subset: `initialize`, `ping`, `tools/list`, `tools/call`, empty `resources/*` and `prompts/list`, `-32601` for the rest; `call_tool` (scope → schema → limits → handler → `{note, data}` result or `isError` envelope → `mcp_tool_called`). |
| `sessions.py` | Signed `Mcp-Session-Id` bound to the token id; nothing stored. |
| `errors.py` | JSON-RPC codes, `RpcError`, the two MCP-only envelope codes (`confirmation_required`, `has_responses`), `UNTRUSTED_NOTE`. |
| `tools/registry.py` | `Tool`, `@tool(...)`, `args_model(base, **ids)`, `inline_refs`, `tools_for(principal)`. |
| `tools/account.py`, `surveys.py`, `sections.py`, `questions.py`, `imports.py` | The handlers -- the REST routes' glue (`api.v1.deps`, `forms_bridge`, `out`, the public helpers of `api.v1.surveys`) over the services. |
| `urls.py` | `/mcp`, `/mcp/`, `/.well-known/oauth-protected-resource/mcp`. |

## Transport rules (stateless Streamable HTTP)

- One `POST` per JSON-RPC message; one `application/json` response. **No SSE stream is ever
  opened**: `GET`/`DELETE` are `405 Allow: POST`. A gthread worker held by a stream for minutes
  is the 2026-09-18 outage again; this is a requirement, not an optimisation.
- Notifications (and client responses) are `202` with an empty body. A batch (`2025-03-26`
  clients) is answered with a list.
- Protocol versions `2025-11-25`, `2025-06-18`, `2025-03-26`: `initialize` answers the client's
  when supported, else the newest; an `MCP-Protocol-Version` header naming another version is
  `400` with `data.supported`; no header = `2025-03-26`. A 2026-07-28 client probing
  `server/discover` gets `-32601`, which that revision defines as "legacy server, fall back to
  `initialize`".
- `Mcp-Session-Id`: issued on `initialize` as `signing.dumps({'t': token_id, 'n': nonce})`. May be
  omitted later; a present id that does not verify or belongs to another token is `404` (the client
  re-initialises). The nonce keys the per-session cap.
- `Origin`: absent is fine (none of the real clients sends one); present and not the issuer's origin
  or in `MCP_ALLOWED_ORIGINS` is `403`.

## Adding a tool

```python
@tool(
    'rename_layer',                      # snake_case, creator vocabulary ("unpublished changes", never "draft")
    title='Rename a layer',
    description='…static text; never built from survey content…',
    scope=scopes.SURVEYS_WRITE,          # None only for get_me
    role='editor',                       # documentation; the check is deps.survey(..., role=)
    args=args_model('RenameLayerArgs', LayerPatchIn, survey=SURVEY, layer_id=(int, Field(...))),
    read_only=False, destructive=False, idempotent=True, confirm=False,
)
def rename_layer(request, args):
    obj = survey(request, args.survey, role='editor')        # 404 / forbidden_role / pro_required
    layer = deps.layer(request, obj, args.layer_id)         # always THROUGH the survey
    svc_layers.rename(actor(request), layer, args.name)     # the service, never the model
    return out.layer(layer, obj)
```

Then `python scripts/build_mcp_reference.py` (the help page is generated; `test_reference` fails
otherwise) and a test per scenario in `mcp/tests/`. Rules the registry does not enforce for you:

- an argument model is built from the REST `In` schema when one exists, so the two surfaces accept
  the same bodies; a new shape goes into `api/v1/schemas.py` first;
- anything irreversible takes `confirm: bool = False`, raises `errors.confirmation_required()`
  without it and is `destructive=True, confirm=True` in the registry;
- a tool result is whatever JSON the handler returns; `call_tool` wraps it as
  `{"note": UNTRUSTED_NOTE, "data": …}`. Never return respondent answer text from a tool in this
  package without a decision on #306's follow-up (response-reading tools);
- raise `ApiError` for refusals; let `survey.services.errors` propagate (mapped by
  `api.v1.errors.from_service_error`, so the codes are the REST codes).

## Errors

Protocol errors are JSON-RPC errors: `-32700` parse, `-32600` invalid request, `-32601` unknown
method, `-32602` unknown tool or arguments failing the schema (`data.fields`), `-32000`
unsupported version (`400`), `-32001` session unknown (`404`), `-32002` origin refused (`403`),
`-32003` a limit on a protocol method (`429`). Tool refusals are `isError` results whose single
text block (and `structuredContent`) is the REST envelope.

## Limits

`tools/call`: `limits.check_request(principal, 'GET' | 'POST')` by `read_only`, then
`limits.check_group('mcp.session', key)` (300 / 10 min; `API_RATE_LIMITS['mcp.session']`
overrides). `initialize`, `tools/list`, `ping` count as reads. The handlers hit the named caps
(`survey_create`, `survey_delete`, `survey_import`) like the routes.

## Tests

`./run_tests.sh mcp` — `test_transport`, `test_auth`, `test_tools`, `test_destructive`,
`test_injection`, `test_limits`, `test_import`, `test_reference`; `tests/helpers.py` has
`McpClient` (bearer + version + session), `data_of` / `error_of`, `MCP_SETTINGS` (issuer and
resources follow the test client's host).

## Operations

No env var is required (`MCP_RESOURCE_URL` defaults to `<issuer>/mcp`; set it only when the server
moves to its own host, together with what clients type). After a deploy: the `401` challenge and the
metadata document with a bot-shaped curl, `scripts/oauth_reachability_check.py`, then the client
matrix (Claude Code, Claude Desktop, Cursor with a token; claude.ai and ChatGPT through OAuth).
