## Why

claude.ai cannot connect to the MCP server (#404): its Client ID Metadata Document declares
`grant_types: ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:jwt-bearer"]`,
and django-oauth-toolkit's CIMD resolver accepts exactly one non-refresh grant type, so no
application is created and `/oauth/authorize` answers "Invalid client_id parameter value." That
blocks the one-button Claude path that change `agent-onboarding` just shipped.

## What Changes

- `api.oauth.dcr.normalise_metadata` — run by both the CIMD fetcher and DCR before the toolkit —
  keeps only the grant types this server issues (`authorization_code`, `refresh_token`) when at
  least one of them is declared, and drops the rest (extension grants such as `jwt-bearer`).
- A document or registration that declares no supported grant type is left as it is, so the
  toolkit still refuses it.

## Capabilities

### New Capabilities

### Modified Capabilities
- `oauth-client-registration`: client metadata with extra, unsupported grant types is accepted
  with those types ignored, on both CIMD and DCR.

## Impact

`api/oauth/dcr.py`, `api/tests/`. No migration, no setting. Production recovers on deploy: the
toolkit's 60-second failure backoff on the claude.ai URL expires by itself.
