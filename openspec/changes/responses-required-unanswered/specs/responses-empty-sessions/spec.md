## MODIFIED Requirements

### Requirement: One definition of an empty session
A session SHALL be empty when it has no `Answer` row with `parent_answer_id IS NULL`. Answers about
layer objects and answers a moderator hid SHALL count as answers. The Responses page, the
completion definition (`responses-required-unanswered`) and the data export SHALL decide
emptiness through one shared helper, so they never disagree about which sessions are empty.

#### Scenario: Object answer makes a session non-empty
- **WHEN** a session's only answer is a reaction to a layer object (`layer_object` set, no parent)
- **THEN** the session is not empty on the Responses page and is present in the export

#### Scenario: Hidden answer still counts
- **WHEN** a session's only answer was hidden by the creator's moderation
- **THEN** the session is not empty

#### Scenario: Geo sub-answer alone does not count
- **WHEN** a session has no top-level answer at all
- **THEN** the session is empty, the Responses page shows it with the "Empty" badge when empty
  sessions are shown, the export leaves it out, and it never counts as completed
