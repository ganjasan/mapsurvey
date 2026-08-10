# survey-cards

## ADDED Requirements

### Requirement: Card response counts span all versions
Dashboard survey cards (grid and list views) SHALL display started/completed counts and
the completion rate aggregated across the canonical survey and all of its version
copies. The counts MUST be computed without per-card N+1 queries.

#### Scenario: Card counts unchanged by publishing
- **GIVEN** a survey card showing "340 started · 104 completed"
- **WHEN** the creator publishes a new version
- **THEN** the card still shows "340 started · 104 completed" (plus any new sessions)
