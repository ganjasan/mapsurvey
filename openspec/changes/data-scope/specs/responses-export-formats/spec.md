## ADDED Requirements

### Requirement: On-hold sessions are exported only with include_all
Every export format SHALL leave out sessions whose validation status is `on_hold`, like trashed
and `not_approved` sessions, unless the request carries `include_all=1`. The API's export link,
response summary, text answers and per-question GeoJSON, which count what the export contains,
SHALL follow the same rule. The export dialog's explanation under "Include excluded responses"
SHALL name on-hold responses together with trashed and not-approved ones.

#### Scenario: On-hold session absent by default
- **WHEN** a survey has 3 approved answered sessions and 1 answered `on_hold` session and a creator
  requests `?format=xlsx`
- **THEN** the `sessions` sheet has 3 rows

#### Scenario: include_all brings it back
- **WHEN** the same request carries `include_all=1`
- **THEN** the `sessions` sheet has 4 rows

#### Scenario: API summary equals the file
- **WHEN** an API client reads the response summary of that survey without `include_all`
- **THEN** the summary counts 3 responses

#### Scenario: Dialog names on-hold responses
- **WHEN** the creator opens the export dialog
- **THEN** the text under "Include excluded responses" says trashed, on-hold and not-approved
  responses are left out unless the switch is on
