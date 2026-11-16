## ADDED Requirements

### Requirement: Every report is reached by its own address
The system SHALL serve every report's editor at `/editor/reports/<uuid>/` and SHALL keep a survey's
Public results tab as a second way into the same editor for that survey's report.

#### Scenario: The two ways show the same blocks
- **WHEN** a survey's report is opened through the survey's tab and at the report's own address
- **THEN** both pages list the same blocks
