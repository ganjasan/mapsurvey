## ADDED Requirements

### Requirement: Activation is emitted on the direct-activation path
The system SHALL send `user_activated` after a successful activation on the confirmation page
(`DirectActivationView`), so that `creator_activated_account` is emitted with
`timestamp_source='live'`. A replayed key that hits the already-activated branch SHALL NOT emit.

#### Scenario: Confirmation POST emits exactly one activation event
- **WHEN** an inactive creator posts a valid activation key to the confirmation page
- **THEN** exactly one `creator_activated_account` is emitted for that creator, the account is
  active and the user is signed in

#### Scenario: Replayed key emits nothing
- **WHEN** the same key is posted again after activation
- **THEN** no activation event is emitted
