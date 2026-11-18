## MODIFIED Requirements

### Requirement: A block readers do not see says why
The canvas SHALL keep a block that readers do not see — hidden by the author, not filled in, or
about a question that no longer exists — and SHALL say which of the three it is.

#### Scenario: A hidden block
- **WHEN** a text block is marked hidden
- **THEN** the canvas shows it with a note that readers do not see it, and the report's page leaves it out

#### Scenario: An empty quotes block
- **WHEN** a quotes block has no quote
- **THEN** the canvas shows it with two actions, "Pick from answers" and "Write a quote", and a line that readers see nothing until it has one; no empty quote row
