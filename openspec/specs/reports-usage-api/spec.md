# reports-usage-api Specification

## Purpose
Reader counts for a report (page opened, embedded, PDF downloaded — per day, no visitor stored, members not counted), workspace tags on reports, and reports in REST API v1 and MCP through the report services, with a confirmation before publishing quotes or individual marks. Implementation: `reports/usage.py`, `reports/blocks.py`, `api/v1/reports.py`, `mcp/tools/reports.py`; tests `survey/tests/test_reports_usage_api.py`.
## Requirements
### Requirement: A report counts how often it is read
The system SHALL count, per report and per day, the times its public page was opened, the times it
(or one of its blocks) was shown inside another site, and the times its stored PDF was downloaded.
It SHALL store nothing about the visitor, SHALL NOT count a signed-in member of the report's
workspace, and SHALL show the totals and the last 30 days in the report editor's Settings.

#### Scenario: An anonymous reader
- **WHEN** an anonymous visitor opens a published report twice and its embedded form once
- **THEN** the report's counts are 2 opened and 1 embedded

#### Scenario: The author
- **WHEN** a signed-in member of the report's workspace opens the published report
- **THEN** no count changes

#### Scenario: The editor shows the numbers
- **WHEN** an editor opens the report's editor after those visits
- **THEN** the Readers card shows the counts

### Requirement: A report takes workspace tags
The system SHALL let an editor set a report's tags from the workspace's tags, creating a tag on
first use, SHALL show them on the Reports list, and SHALL filter the list by a tag.

#### Scenario: Tagging a report
- **WHEN** an editor saves a report's settings with the tags "Riverside, 2027"
- **THEN** the report carries both tags and the Reports list filtered by "riverside" lists it and not an untagged report

### Requirement: Reports in REST API v1
The system SHALL expose reports at `/api/v1/reports`: list, create (empty, or drafted from a survey
by a template), read with blocks and reader counts, change settings, add, change, reorder and delete
blocks, read the pre-publication checks, publish, freeze and delete. Every write SHALL go through
the report services, SHALL need the editor role on the report and the Reports feature of its
workspace, and a report the caller may not see SHALL answer 404.

#### Scenario: Draft, write and publish
- **WHEN** a token of a workspace editor creates a report from a survey with the template `summary`, adds a text block and a chart block of a question code, and publishes it
- **THEN** the report is published and its public page shows the text and the chart

#### Scenario: Quotes need a confirmation
- **WHEN** the token publishes a report that shows a quote without `confirm`
- **THEN** the answer is 409 and the report stays unpublished; with `confirm: true` it is published

#### Scenario: A block the survey cannot back
- **WHEN** the token adds a chart block naming a question code the survey does not have
- **THEN** the answer is 422 naming `question` and no block is added

#### Scenario: Another workspace's report
- **WHEN** a token of a member of another workspace reads the report
- **THEN** the answer is 404

#### Scenario: Without the Reports feature
- **WHEN** a token of a workspace whose trial is over adds a block
- **THEN** the answer is 403 `pro_required` and no block is added

### Requirement: Reports in MCP
The system SHALL offer the same operations as MCP tools, hidden from tokens without their scope.
`publish_report` SHALL refuse with `confirmation_required` a report that shows quotes or individual
marks until `confirm` is true, and `delete_report` SHALL refuse without `confirm`.

#### Scenario: An agent writes a report
- **WHEN** an agent creates a report from a survey, adds a numbers block with a `{responses}` token, reads the checks and publishes
- **THEN** the report is published and its page shows the filled number

#### Scenario: Confirmation
- **WHEN** an agent calls `delete_report` without `confirm`, then `publish_report` on a report with a visible quote without `confirm`
- **THEN** both answer `confirmation_required` and nothing changes

