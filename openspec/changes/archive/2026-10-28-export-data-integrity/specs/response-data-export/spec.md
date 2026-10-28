## ADDED Requirements

### Requirement: Each exported value derives only from its own question

Every cell in the CSV and every property in a GeoJSON feature SHALL be derived solely from the
answer rows belonging to that question. A question with no answer row, or whose answer carries no
value, SHALL export as empty — never as the value of another question.

#### Scenario: Sub-question left blank exports empty, not the neighbour's value

- **WHEN** a geo answer has two sub-questions in order, the first answered "Lärm" and the second
  left blank so that no `Answer` row exists for it
- **THEN** the GeoJSON feature's properties contain `"Lärm"` under the first sub-question's name
- **AND** an empty value under the second sub-question's name

#### Scenario: Several consecutive blank sub-questions all export empty

- **WHEN** a geo answer has an answered sub-question followed by three sub-questions with no
  `Answer` rows
- **THEN** all three export as empty values, and none carries the answered sub-question's value

#### Scenario: Sub-question of a display-only type does not absorb a neighbour's value

- **WHEN** a geo answer has an answered text sub-question followed by an `html` sub-question
- **THEN** the `html` sub-question exports as empty

#### Scenario: Number sub-question exports its own value

- **WHEN** a respondent places a point and enters `7` in a `number` sub-question
- **THEN** the feature's properties contain `7` under that sub-question's name

### Requirement: Answers of every value-bearing type reach the export

The export SHALL emit a column or property for each question whose type can hold respondent input:
`text`, `text_line`, `number`, `range`, `choice`, `rating`, `multichoice`, `datetime`. No such
answer may be omitted from the download.

#### Scenario: datetime answer appears in the CSV

- **WHEN** a respondent answers a `datetime` question and the creator downloads the data
- **THEN** the CSV contains a column named after that question
- **AND** the row holds the answered moment serialised as ISO 8601

#### Scenario: datetime value that cannot be parsed is passed through, not dropped

- **WHEN** a `datetime` answer holds a string that does not parse as a datetime
- **THEN** the CSV cell contains that string unchanged

#### Scenario: choice answer exports the choice name, not its code

- **WHEN** a respondent selects a choice whose code is `2` and whose name is "Ruhig"
- **THEN** the CSV cell contains `Ruhig`

#### Scenario: multichoice answer exports all selected names

- **WHEN** a respondent selects two options of a `multichoice` question
- **THEN** the CSV cell contains both names separated by `"; "`

### Requirement: Types excluded from the CSV are excluded deliberately

Geometry questions (`point`, `line`, `polygon`) SHALL NOT produce CSV columns, because their answers
are exported as GeoJSON layers. Display-only questions (`image`, `html`) SHALL NOT produce CSV
columns, because they carry no respondent input.

#### Scenario: Geo question produces a layer, not a CSV column

- **WHEN** a survey has a `point` question and responses exist
- **THEN** the ZIP contains a `.geojson` file for that question
- **AND** the CSV has no column named after it

#### Scenario: Display-only question produces no CSV column

- **WHEN** a survey has an `html` question
- **THEN** the CSV has no column named after it

### Requirement: An unrecognised question type is visible, not silent

If a question's type belongs to none of the classified sets, the export SHALL still emit a column
named after that question, holding an empty value, and SHALL log a warning naming the unrecognised
type. The download SHALL NOT fail.

#### Scenario: Unclassified type yields an empty column and a warning

- **WHEN** a question carries an `input_type` that the export does not classify
- **THEN** the CSV contains a column named after that question with empty values
- **AND** a warning naming the unrecognised type is logged
- **AND** the response is a valid ZIP with status 200

### Requirement: Session metadata identifies the responding session

Each CSV row and each GeoJSON feature SHALL carry the session identifiers of the response it came
from, taken from that response's own session.

#### Scenario: GeoJSON feature reports the session that submitted it

- **WHEN** two sessions each place a point with answered sub-questions
- **THEN** each feature's `session_id` property is that of the session which submitted it
- **AND** each feature's `validation_status` and `language` properties come from the same session
