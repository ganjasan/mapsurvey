## ADDED Requirements

### Requirement: One builder decides which sessions a surface counts
The system SHALL obtain every set of survey sessions it reads — counts, aggregates, tallies,
exports, API and MCP response scopes, Responses statistics — from `data.scope.SessionScope`.
The scope SHALL take survey ids (version resolution stays with the caller) and named switches:
`include_deleted` (keep trashed sessions), `include_moderated` (keep `on_hold` and `not_approved`
sessions), `nonempty` (only sessions with a top-level answer), `completed_headers` (only sessions
that answered their version's last section) and `external_only` (only sessions opened by people
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

### Requirement: Each surface uses its named scope
The public results page and Site results blocks SHALL count clean, non-empty sessions of the
survey family. Shared-map objects and their tallies SHALL count clean sessions. Responses and the
object statistics it shows SHALL count non-trashed sessions including moderated ones. The export
SHALL keep non-empty sessions that are clean, or every non-empty session when `include_all` is
set. The API's response scope SHALL be the export's. The API structure's response count SHALL
count non-trashed, non-empty sessions; the MCP survey response count SHALL count non-trashed,
non-empty external sessions.

#### Scenario: Public results and Responses agree on answered responses
- **WHEN** a survey has 5 approved answered sessions and 2 approved empty ones
- **THEN** the public results counter shows 5 and the Responses headline shows 5 responses

#### Scenario: API structure count ignores trashed sessions
- **WHEN** a survey has 4 answered sessions, one of them trashed
- **THEN** the API survey structure reports 3 responses

### Requirement: No new hand-written session filter outside data
A test SHALL scan every non-test, non-migration Python module of the product packages outside
`data/` for hand-written session filters (a keyword `is_deleted=` filter, a `__is_deleted`
lookup, a `validation_status__in` filter, an exclusion by validation status, the empty-session
predicate) and SHALL fail when a module is not on the allow-list or holds more such filters than
the list records. The allow-list SHALL give a reason per module (a single-session lookup, a staff
dashboard, the model definition) and SHALL only shrink: a module holding fewer filters than
recorded SHALL fail the test until its entry is lowered or removed.

#### Scenario: A new copy fails the build
- **WHEN** a developer adds `Answer.objects.filter(survey_session__is_deleted=False)` to a module
  outside `data/`
- **THEN** the guard test fails and names the module

#### Scenario: A removed copy must shrink the list
- **WHEN** a module on the allow-list loses one of its filters
- **THEN** the guard test fails until that module's recorded count is lowered
