## ADDED Requirements

### Requirement: The report file carries live blocks
The report file SHALL record a cross-tab block by its survey and the two question codes, an
engagement block by its survey, and a map block's choice to show marks; an import SHALL make the
blocks again with their views where the workspace has the survey, and leave them out with a message
otherwise.

#### Scenario: Round trip of a cross-tab and a map with marks
- **WHEN** a report with a cross-tab, an engagement block and a map showing marks is exported and imported in the same workspace
- **THEN** the copy has the three blocks, the cross-tab on the same two questions and the map still showing marks

#### Scenario: Into a workspace without the survey
- **WHEN** that file is imported into another workspace
- **THEN** the three blocks are left out and the member is told
