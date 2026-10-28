## Why

ChatGPT cannot connect to the MCP server: `/oauth/authorize` answers "Invalid client_id parameter
value." (2026-10-25, production). ChatGPT identifies itself with a Client ID Metadata Document,
`https://chatgpt.com/oauth/client.json`, which declares `token_endpoint_auth_method:
"private_key_jwt"` and lists `["none", "private_key_jwt"]` in `token_endpoint_auth_methods_supported`.
django-oauth-toolkit registers only public CIMD clients (`"none"`), so no application is created.
Our server metadata advertises no `private_key_jwt`, so ChatGPT would authenticate as a public
client with PKCE at the token endpoint anyway.

Two copy defects ride along: the ChatGPT steps say to press "+" where ChatGPT's button reads "Add",
and a two-line `{# #}` comment on `/editor/account/connections/` is printed on the page.

## What Changes

- `api.oauth.cimd.MetadataFetcher` registers a document as a public client (`"none"`) when its
  `token_endpoint_auth_methods_supported` includes `"none"`, dropping the key-auth members. A client
  that cannot be public is still refused. DCR is unchanged.
- ChatGPT step: "press [[Add]]" in `survey/agent_clients.py`, the ten catalogs that carry it and the
  help page.
- `api/templates/api/connections.html`: the comment becomes `{% comment %}`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `oauth-client-registration`: a CIMD client that names a key-based token method but supports
  `none` is registered as a public client.

## Impact

`api/oauth/cimd.py`, `api/tests/`, `survey/agent_clients.py`, `survey/locale/*`, `help/`,
`api/templates/api/connections.html`. No migration, no setting. Production recovers on deploy:
the toolkit's 60-second failure backoff on the ChatGPT URL expires by itself.
