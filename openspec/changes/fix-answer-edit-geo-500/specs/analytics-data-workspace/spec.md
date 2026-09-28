## ADDED Requirements

### Requirement: Inline answer editing is limited to single-value types

The inline answer edit endpoint SHALL accept only question types in the shared editable list
(`text`, `text_line`, `number`, `range`, `choice`, `multichoice`, `rating`, `datetime`) and SHALL
reject any other type with HTTP 400 without reading or writing answers. For an editable type it
SHALL update the earliest existing root answer of that session and question, or create one when
none exists, and SHALL NOT fail when more than one root answer exists. The Responses table SHALL
offer inline editing only on columns of an editable type.

#### Scenario: Editing a multi-feature geo answer is refused, not crashed

- **GIVEN** a session with three root answers to a `point` question
- **WHEN** an editor POSTs a new value for that session and question
- **THEN** the response is 400 and the three answers are unchanged

#### Scenario: Editing an unanswered geo question creates nothing

- **GIVEN** a session with no answer to a `polygon` question
- **WHEN** an editor POSTs a value for it
- **THEN** the response is 400 and no answer row is created

#### Scenario: Editing a text answer still works and tolerates duplicates

- **GIVEN** a session with two root answers to a `text` question
- **WHEN** an editor POSTs `"new"` for it
- **THEN** the response is 204 and the earliest answer's text is `"new"`

#### Scenario: Geo columns are not editable in the table

- **WHEN** the Responses table renders a `point` column and a `text` column for an editor
- **THEN** only the text cells carry the double-click edit handler
