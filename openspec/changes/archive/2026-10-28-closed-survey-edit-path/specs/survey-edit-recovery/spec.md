## ADDED Requirements

### Requirement: A closed survey can be taken back into editing via a draft copy

An owner SHALL be able to create a draft copy of a `closed` survey, on the same terms as a
`published` one. The editor SHALL offer this route wherever the survey is read-only.

#### Scenario: Draft copy created from a closed survey

- **WHEN** an owner creates a draft copy of a closed survey
- **THEN** the draft is created and linked to it
- **AND** the closed survey itself is unchanged

#### Scenario: The read-only banner offers the route

- **WHEN** an owner opens a closed survey that has no draft copy
- **THEN** the read-only notice offers to create one

#### Scenario: An existing draft is linked rather than duplicated

- **WHEN** an owner opens a closed survey that already has a draft copy
- **THEN** the read-only notice links to that draft
- **AND** a second draft cannot be created

### Requirement: Publishing a draft never reopens a closed survey

Publishing a draft of a `closed` survey SHALL apply the changes and leave the survey closed.
Accepting responses again SHALL remain a separate, explicit action.

#### Scenario: Closed survey stays closed after its draft is published

- **WHEN** a draft copy of a closed survey is published
- **THEN** the canonical survey carries the draft's structure
- **AND** its status is still `closed`
- **AND** its version number has increased

#### Scenario: The previous version is archived as usual

- **WHEN** a draft copy of a closed survey is published
- **THEN** the previous structure and its sessions are moved to an archived version, exactly as for
  a published survey

### Requirement: A survey that has collected nothing can be returned to draft

`published → draft` and `closed → draft` SHALL be permitted only while the survey has no sessions of
its own and no archived versions. Otherwise they SHALL be refused.

#### Scenario: Accidental publish is undone

- **WHEN** an owner returns a published survey with no sessions and no archived versions to draft
- **THEN** the transition succeeds
- **AND** the survey becomes editable again

#### Scenario: A survey with responses cannot be returned to draft

- **WHEN** an owner attempts to return a published survey that has sessions to draft
- **THEN** the transition is refused
- **AND** the survey's status is unchanged

#### Scenario: A survey with earlier versions cannot be returned to draft

- **WHEN** an owner attempts to return a survey to draft that has no sessions of its own but does
  have an archived version
- **THEN** the transition is refused

  Sessions move onto the archived header when a new version is published, so a canonical survey can
  show zero sessions while the survey has collected plenty.

#### Scenario: A closed survey that collected nothing can be returned to draft

- **WHEN** an owner returns a closed survey with no sessions and no archived versions to draft
- **THEN** the transition succeeds

### Requirement: The read-only notice always names an available action

Wherever a survey is read-only, the editor SHALL name what the author can do next rather than only
stating that editing is blocked.

#### Scenario: Locked survey without a draft

- **WHEN** an owner opens a read-only survey that has no draft copy
- **THEN** the notice offers to create one

#### Scenario: Locked survey that collected nothing

- **WHEN** an owner opens a read-only survey with no sessions and no archived versions
- **THEN** the notice offers to return it to draft
