# response-data-export — delta for operator-entry

## MODIFIED Requirements

### Requirement: Session metadata identifies the responding session

Each CSV row and each GeoJSON feature SHALL carry the session identifiers of the response it came
from, taken from that response's own session. Session-level tables (the `sessions` sheet of the
workbook and the sessions CSV) SHALL carry the session's `source` and `entered_by` (the operator's
username, blank for online sessions) beside `opened_by_kind`.

#### Scenario: GeoJSON feature reports the session that submitted it

- **WHEN** two sessions each place a point with answered sub-questions
- **THEN** each feature's `session_id` property is that of the session which submitted it
- **AND** each feature's `validation_status` and `language` properties come from the same session

#### Scenario: Sessions table carries the source

- **GIVEN** one online session and one session entered from paper by operator `clerk`
- **WHEN** the workbook export runs
- **THEN** the `sessions` sheet reads `online` / blank for the first and `paper` / `clerk` for the second
