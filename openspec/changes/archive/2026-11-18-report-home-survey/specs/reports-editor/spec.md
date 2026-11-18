## ADDED Requirements

### Requirement: A block can come from any survey of the workspace
The system SHALL let the author choose, in the block library, the survey whose charts, maps,
cross-tab, engagement and comparison are offered, among the published surveys of the workspace the
member sees. The library SHALL start on the report's home survey; for a report without one it
SHALL start on the workspace's only such survey, and otherwise ask for a survey. Choosing another
survey SHALL NOT change the report's home survey.

#### Scenario: A blank report shows a chart
- **WHEN** an editor opens "Add block" in a report without a home survey, chooses a survey and picks one of its choice questions
- **THEN** the report has a chart of that question

#### Scenario: A second survey in the same report
- **WHEN** an editor of a report whose home survey is A chooses survey B in the library and picks one of B's questions
- **THEN** the report has a block reading B and its home survey is still A

#### Scenario: A survey of another workspace
- **WHEN** a block is posted with a survey of another workspace as its source
- **THEN** nothing is added

### Requirement: A report's home survey can be set, changed and cleared
The system SHALL make the survey of the first data block added to a report without a home survey
that report's home survey, when the author has the editor role on that survey. Report settings
SHALL show the home survey and let an editor set, change or clear it, offering only surveys the
member may edit; clearing SHALL keep every block. The "Take the survey" and "Link from the thanks
page" switches SHALL be shown only while the report has a home survey, and their stored values
SHALL survive a save made without them. A report somebody started SHALL NOT be filled with drafted
blocks by its survey's Public results tab.

#### Scenario: The first data block sets the home survey
- **WHEN** an editor adds a chart of a question of survey A to a report without a home survey
- **THEN** the report's home survey is A

#### Scenario: Setting it in settings
- **WHEN** an editor chooses survey A in the Survey card of Report settings
- **THEN** the report's home survey is A and the library offers A's questions

#### Scenario: Clearing it
- **WHEN** an editor chooses "No survey" for a report with three blocks
- **THEN** the report has no home survey and still has its three blocks

#### Scenario: A survey the member only views
- **WHEN** a member without the editor role on survey A posts A as the report's home survey
- **THEN** the home survey is unchanged

#### Scenario: Switches without a survey
- **WHEN** a report without a home survey is opened in the editor and its settings are saved
- **THEN** the two survey switches are not shown and their stored values are unchanged

#### Scenario: An adopted blank report is not drafted over
- **WHEN** a blank report becomes the only report of a published survey and the survey's Public results tab is opened
- **THEN** the report has no blocks it was not given by its author
