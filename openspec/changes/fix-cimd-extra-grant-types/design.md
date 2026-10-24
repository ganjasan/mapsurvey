## Context

django-oauth-toolkit maps RFC 7591 metadata onto `Application.authorization_grant_type`, a single
value, so both its CIMD resolver and its DCR view refuse metadata with more than one non-refresh
grant type. Real clients advertise extension grants they may use elsewhere: claude.ai lists
`urn:ietf:params:oauth:grant-type:jwt-bearer`. Our `normalise_metadata` already runs on both paths
before the toolkit (`MetadataFetcher.fetch`, `rewrite_body`).

## Goals / Non-Goals

**Goals:** accept such clients as public authorization-code clients; keep refusing clients that
declare nothing we issue.

**Non-Goals:** supporting jwt-bearer or any other grant; patching the toolkit.

## Decisions

### D1 · Filter in our normaliser, not in the toolkit
One function both paths already call; no monkey-patching of `oauth2_provider.cimd`, so a toolkit
upgrade cannot silently undo it. RFC 7591 §2 lets the authorization server ignore or replace
metadata values it does not support. *Alternative*: subclass the CIMD resolver — rejected, it is a
module-level function, not a setting.

### D2 · Leave an unsupported-only list untouched
Filtering `["client_credentials"]` to `[]` would make the toolkit default to authorization_code and
silently register a client that asked for something else. Passing it through keeps the refusal.

## Risks / Trade-offs

- [A client relies on a dropped grant] → It never worked here; the stored metadata now says so.
