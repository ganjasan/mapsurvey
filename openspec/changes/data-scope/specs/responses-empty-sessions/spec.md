## MODIFIED Requirements

### Requirement: One definition of an empty session
A session SHALL be empty when it has no `Answer` row with `parent_answer_id IS NULL`. Answers about
layer objects and answers a moderator hid SHALL count as answers. The Responses page, the session
issue computation, the data export and the public results page SHALL decide emptiness through one
shared predicate — the `nonempty` switch of the session scope (`session-scope`) — so they never
disagree about which sessions are empty.

#### Scenario: Object answer makes a session non-empty
- **WHEN** a session's only answer is a reaction to a layer object (`layer_object` set, no parent)
- **THEN** the session is not empty on the Responses page and is present in the export

#### Scenario: Hidden answer still counts
- **WHEN** a session's only answer was hidden by the creator's moderation
- **THEN** the session is not empty

#### Scenario: Geo sub-answer alone does not count
- **WHEN** a session has no top-level answer at all
- **THEN** the session is empty, and the `empty` issue, the export and the public results page
  agree on it

## ADDED Requirements

### Requirement: The headline names moderated responses
Responses SHALL keep showing sessions that are `on_hold` or `not_approved` (the creator moderates
there), and when the shown scope holds any, the headline SHALL say how many: "including N on hold"
and/or "M not approved". Nothing SHALL be added when the scope holds none.

#### Scenario: Moderated responses are named
- **WHEN** a survey has 10 shown responses of which 2 are on hold and 1 is not approved
- **THEN** the headline shows 10 responses and states 2 on hold and 1 not approved

#### Scenario: Nothing to name
- **WHEN** no shown response is on hold or not approved
- **THEN** the headline carries no moderation line
