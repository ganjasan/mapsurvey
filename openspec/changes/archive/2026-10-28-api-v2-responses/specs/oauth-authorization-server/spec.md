## ADDED Requirements

### Requirement: Moderation is a switch on the consent page
When a client requests `responses:moderate`, the consent page SHALL show it with the publish and
delete switches, off by default, with its own note that it can be changed back ("Rejected responses
leave exports and public results; you can change it back.") instead of "This cannot be undone".
Allowing without ticking it SHALL issue a code without `responses:moderate`.

#### Scenario: Moderation off by default
- **WHEN** a client requests `responses:read responses:moderate` and the user allows without ticking
- **THEN** the issued scope is `responses:read`

#### Scenario: Its own note
- **WHEN** the consent page shows the moderation switch
- **THEN** its note does not say "cannot be undone"
