# draft-copy-lifecycle — delta for fix-publish-fetch-silent-failure

## ADDED Requirements

### Requirement: Publishing a draft never fails silently

The publish-draft flow SHALL give the creator visible feedback for every outcome of its
requests. When the compatibility-check request or the publish request cannot complete —
network failure, blocked request, or a non-OK response whose body is not the expected JSON —
the creator MUST see an error message; the button MUST NOT silently do nothing.

#### Scenario: Compatibility check request fails at network level

- **WHEN** the creator clicks "Publish draft" and the compatibility-check request is blocked
  or the network is down
- **THEN** a visible message tells the creator the server could not be reached and suggests
  checking the connection and any ad blocker

#### Scenario: Compatibility check returns a non-OK response

- **WHEN** the compatibility-check endpoint answers with an error status (e.g. a 500 page)
- **THEN** the same visible failure message is shown and no attempt is made to parse the
  body as JSON

#### Scenario: Publish request fails at network level

- **WHEN** the creator confirms publishing and the publish POST is blocked or the network
  is down
- **THEN** the same visible failure message is shown

#### Scenario: Existing HTTP-status error handling is preserved

- **WHEN** the publish POST answers with an error status (409 translation gaps, 409
  compatibility, other errors)
- **THEN** the existing status-specific messages are shown unchanged
