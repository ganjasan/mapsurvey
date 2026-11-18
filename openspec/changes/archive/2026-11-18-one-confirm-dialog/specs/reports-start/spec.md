## MODIFIED Requirements

### Requirement: A report starts from a card
The system SHALL let an editor of a workspace start a blank report in one click: "New report" on the
Reports list creates it and opens it in the editor. The start page SHALL offer the blank report
only; the arrangements drafted from a survey and the copy of an earlier report SHALL NOT be offered
on it for now, while the same address keeps creating them for callers that ask (the API, MCP and
earlier links). Members who may not edit SHALL not reach the start page.

#### Scenario: One click drafts a report
- **WHEN** a "Consultation summary" draft of a survey is asked for at the start address
- **THEN** a new unpublished report of that survey exists and its editor opens

#### Scenario: A blank report
- **WHEN** an editor presses "New report" on the Reports list, or "Blank report" on the start page
- **THEN** an unpublished report without a home survey opens in the editor

#### Scenario: A viewer
- **WHEN** a viewer opens the start page
- **THEN** the answer is 404

#### Scenario: No survey to draft from
- **WHEN** the workspace has no published survey
- **THEN** the page offers the blank report and no arrangement
