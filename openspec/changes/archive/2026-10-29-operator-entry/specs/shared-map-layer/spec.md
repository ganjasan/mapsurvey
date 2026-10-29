# shared-map-layer — delta for operator-entry

## ADDED Requirements

### Requirement: Operator sessions are not materialised
`sync_question_layers_for_session` SHALL return without materialising anything for a session
whose `source` is not `online`, and the backfill SHALL skip such sessions. Keyed-in marks join the
shared map only when epic #350 decides so.

#### Scenario: Entered point stays off the layer
- **GIVEN** a reference layer sourced from geo question Q3
- **WHEN** an operator enters a point for Q3 and finishes
- **THEN** the layer has no object keyed to that session

#### Scenario: Backfill skips entered sessions
- **GIVEN** two online sessions and one paper session with points for Q3
- **WHEN** a question layer for Q3 is created and backfilled
- **THEN** the layer has objects for the two online sessions only
