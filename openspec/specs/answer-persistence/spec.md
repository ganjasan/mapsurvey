# answer-persistence Specification

## Purpose

How a submitted section's values become Answer rows: the storage path is chosen by the
question's `input_type` (never by the shape of its `choices`), datetime values persist to
`text`, and no write path can leave a `choices` list on a type that does not use one.

## Requirements

### Requirement: Answer storage is selected by input_type alone

The respondent POST handler SHALL choose how to store each answer — geometry, ranking,
`selected_choices`, `numeric`, or `text` — from the question's `input_type` only. The content of
the question's `choices` field SHALL NOT change which storage path runs, for top-level questions
and sub-questions alike.

#### Scenario: A geo question with leftover choices still saves geometry

- **GIVEN** a `point` question whose `choices` holds a stale non-empty list
- **WHEN** a respondent submits the section with a drawn point
- **THEN** the geometry is saved and the submit succeeds (no 500)

#### Scenario: A text sub-question with leftover choices still saves text

- **GIVEN** a `text` sub-question of a geo question whose `choices` is non-empty
- **WHEN** the respondent's feature properties carry a text value
- **THEN** the value is stored in `text`, not parsed as a choice code

#### Scenario: Choice answers are unaffected

- **WHEN** a respondent submits `choice`, `multichoice`, `rating`, `range`, `number`, `text`
  and `ranking` questions
- **THEN** each stores exactly as before the change

### Requirement: datetime answers persist

A `datetime` answer SHALL be stored in the answer's `text` field, in the submitted
`datetime-local` string form, for top-level questions and sub-questions of geo questions.

#### Scenario: Top-level datetime round-trips

- **WHEN** a respondent submits a datetime value and revisits the section
- **THEN** the stored value prepopulates the field

#### Scenario: Sub-question datetime is not dropped

- **WHEN** a geo feature's properties carry a datetime sub-answer
- **THEN** the sub-answer row holds the value in `text` instead of being empty

### Requirement: choices cannot persist on a type that does not use them

Every write path — question create, question edit, sub-question create, and ZIP import — SHALL
persist `choices = None` for a question whose `input_type` is not one of `choice`, `multichoice`,
`range`, `rating`, `ranking`, regardless of any `choices_json` or serialized choices submitted
alongside it.

#### Scenario: Switching a choice question to point clears its choices

- **GIVEN** a `choice` question with options, edited in the editor
- **WHEN** the creator switches its type to `point` and saves (the form still posting the old
  `choices_json`)
- **THEN** the saved question has `choices = None`

#### Scenario: Importing a poisoned ZIP does not recreate the state

- **WHEN** a ZIP containing a `point` question with a `choices` list is imported
- **THEN** the created question has `choices = None`

#### Scenario: Existing poisoned rows are repaired

- **WHEN** the data migration runs
- **THEN** every question of a non-choice type has `choices = None`
- **AND** choice-bearing types keep their lists untouched
