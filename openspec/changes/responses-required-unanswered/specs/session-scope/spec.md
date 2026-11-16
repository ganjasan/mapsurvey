## MODIFIED Requirements

### Requirement: One builder decides which sessions a surface counts
The system SHALL obtain every set of survey sessions it reads — counts, aggregates, tallies,
exports, API and MCP response scopes, Responses statistics — from `data.scope.SessionScope`.
The scope SHALL take survey ids (version resolution stays with the caller) and named switches:
`include_deleted` (keep trashed sessions), `include_moderated` (keep `on_hold` and `not_approved`
sessions), `nonempty` (only sessions with a top-level answer), `completed` (only completed sessions — not
empty and no required question left unanswered, `responses-required-unanswered`) and `external_only` (only sessions opened by people
outside the workspace). Without switches a scope SHALL be clean: not trashed, not `on_hold`, not
`not_approved`. The same scope SHALL also filter related rows (answers, layer objects) through one
expression, so a related query never restates the rule.

#### Scenario: Default scope is clean
- **WHEN** a survey family has one approved, one `on_hold`, one `not_approved` and one trashed
  session, and a scope is built with no switches
- **THEN** it contains only the approved session

#### Scenario: Switches widen the scope by name
- **WHEN** the same scope is built with `include_moderated=True`
- **THEN** it contains the approved, `on_hold` and `not_approved` sessions but not the trashed one

#### Scenario: Related rows follow the same rule
- **WHEN** answers of that family are filtered with the clean scope's related expression
- **THEN** only answers of the approved session remain

#### Scenario: Completed switch reads the stored state
- **WHEN** a scope of two non-empty sessions, one with a required question unanswered, is built
  with `completed=True`
- **THEN** it contains only the other session
