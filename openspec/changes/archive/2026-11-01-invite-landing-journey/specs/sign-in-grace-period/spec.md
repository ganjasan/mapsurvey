## MODIFIED Requirements

### Requirement: Anything matched by address alone waits for confirmation
Joining a workspace because an invitation was sent to the account's address SHALL happen when the
address is confirmed, not at registration: an account signs in before proving the mailbox, so
anyone could otherwise register with an invited address and walk into that workspace. An
invitation LINK (its token was mailed) SHALL keep working for a signed-in account and for a
registration that carries it (see `workspace-invitation-journey`). When confirmation joins one or
more workspaces, the last one joined SHALL become the active workspace and the confirmation's
redirect SHALL land on its dashboard with the joined banner; the activation view SHALL sign the
account in before the `user_activated` receivers run, so that the session they write survives.
Product mail sent to every creator (the newsletter) SHALL go only to confirmed addresses.

#### Scenario: Registering with an invited address
- **WHEN** someone registers with an address a workspace invited
- **THEN** the account is not a member of that workspace until the address is confirmed, and is
  a member right after confirming

#### Scenario: Confirmation lands in the joined workspace
- **WHEN** an account with an invited address confirms it from the activation link
- **THEN** the redirect reaches `/editor/` with the inviting workspace active and the dashboard
  shows "You've joined <workspace>."

#### Scenario: Newsletter recipients
- **WHEN** a newsletter campaign lists its recipients
- **THEN** an account with an unconfirmed address is not among them
