## ADDED Requirements

### Requirement: An edit that would destroy answers requires explicit acknowledgement

Deleting a question, sub-question or section that has answers attached SHALL NOT proceed unless the
request carries an explicit acknowledgement. Without it the server SHALL refuse the delete, leave
every row intact, and report how many answers the delete would have destroyed.

#### Scenario: Delete without acknowledgement is refused

- **WHEN** a delete is requested for a question that has 3 answers, with no acknowledgement
- **THEN** the response status is 409
- **AND** the response reports 3 answers at risk
- **AND** the question and all 3 answers still exist

#### Scenario: Delete with acknowledgement proceeds

- **WHEN** the same delete is requested with the acknowledgement
- **THEN** the question is deleted
- **AND** its answers are deleted with it

#### Scenario: A question with no answers deletes in one step

- **WHEN** a delete is requested for a question with no answers and no acknowledgement
- **THEN** the question is deleted
- **AND** the response is not a 409

### Requirement: The count includes everything beneath the deleted object

The reported count SHALL include answers to sub-questions of the question being deleted, and — when
a section is deleted — answers to every question in that section and their sub-questions.

#### Scenario: Question count includes its sub-questions' answers

- **WHEN** a delete is requested for a geo question with 2 answers whose sub-question has 5
- **THEN** the reported count is 7

#### Scenario: Section count spans its questions and their sub-questions

- **WHEN** a delete is requested for a section holding two questions with 4 and 6 answers, one of
  which has a sub-question with 3
- **THEN** the reported count is 13

#### Scenario: Section with no answers deletes in one step

- **WHEN** a delete is requested for a section whose questions have no answers
- **THEN** the section is deleted without requiring acknowledgement

### Requirement: The author is told what versioning would have done, when it applies

The confirmation SHALL explain that answers in this survey are not preserved by versioning, and that
once a survey is published, edits go through a draft copy while previous answers are kept as an
archived version.

This explanation SHALL appear only for a survey that has never been published. For a draft copy of a
published survey it SHALL NOT appear, because that author already has version protection and the
statement would be false.

#### Scenario: Never-published survey gets the explanation

- **WHEN** a delete confirmation is raised on a survey with `version_number = 1` and no archived
  versions
- **THEN** the confirmation explains that publishing preserves previous answers as an archived
  version

#### Scenario: Draft copy of a published survey does not

- **WHEN** a delete confirmation is raised on a draft copy of a published survey
- **THEN** the confirmation reports the count without the versioning explanation

### Requirement: Refusing a delete changes nothing

A refused delete SHALL be free of side effects: no question, sub-question, section, answer or
session is modified, and section ordering is unchanged.

#### Scenario: Refused section delete leaves ordering intact

- **WHEN** a delete is requested without acknowledgement for a section that has answers and sits
  between two other sections
- **THEN** the section still exists
- **AND** its neighbours still link to it in the same order as before the request
