## ADDED Requirements

### Requirement: A published report can be framed by the sites its author allows
The system SHALL send, with the page of a published public or unlisted report, a
`frame-ancestors` policy naming the report's allowed hosts — any site when the list is empty — in
place of `X-Frame-Options`, and SHALL keep `X-Frame-Options: SAMEORIGIN` for a workspace-only
report and for every editor page. A host that is not a site address SHALL be refused when saved.

#### Scenario: Any site by default
- **WHEN** a published unlisted report with no allowed hosts is requested
- **THEN** the response allows any ancestor and carries no X-Frame-Options

#### Scenario: An allow-list
- **WHEN** the report's allowed hosts are "city.example.org"
- **THEN** the response's frame-ancestors names https://city.example.org and not every site

#### Scenario: A workspace-only report
- **WHEN** a workspace-only report is opened by a member
- **THEN** the response keeps X-Frame-Options: SAMEORIGIN

#### Scenario: Not a host
- **WHEN** an editor saves "not a host" as an allowed site
- **THEN** the save is refused and the list is unchanged

### Requirement: A framed report tells its host how tall it is
The system SHALL, when a report or block page is requested with `embed=1`, leave out the
visibility ribbon and include the script that posts the content's height to the parent window in
the message format `/embed.js` reads. The page without `embed=1` SHALL not include it.

#### Scenario: Embed mode
- **WHEN** a published report is requested with embed=1
- **THEN** the page posts "mapsurvey" height messages and shows no ribbon

### Requirement: One block has a page of its own
The system SHALL serve one visible block of a published report at its own address, without the
report's opening, under the same access rule and framing policy as the report, and SHALL answer
404 for a block that is hidden or belongs to another report.

#### Scenario: A single chart
- **WHEN** the address of a chart block of a published report is requested
- **THEN** the page shows that chart and neither the report's title nor its other blocks

#### Scenario: A hidden block
- **WHEN** the address of a hidden block is requested
- **THEN** the answer is 404

### Requirement: Report and block links answer oEmbed
The system SHALL answer an oEmbed request for the link of a published public or unlisted report, or
of one of its blocks, with the embed code, and SHALL answer 404 for any other report. The report's
page SHALL carry the oEmbed discovery link.

#### Scenario: A report link
- **WHEN** oEmbed is asked about a published unlisted report's link
- **THEN** the answer is of type rich with an iframe of that report

#### Scenario: A workspace-only report
- **WHEN** oEmbed is asked about a workspace-only report's link
- **THEN** the answer is 404

### Requirement: A block's numbers download as CSV, masked as the page
The system SHALL give the numbers of a chart, cross-tab, engagement, map, key-numbers, budget or
objects block as CSV built from what the page shows: a group the page hides SHALL read "<K" and
its value SHALL not be in the file; a map SHALL list its cells, or its marks only when the author
chose marks. A block without numbers SHALL answer 404. The public address SHALL follow the report's
access rule; an editor SHALL get the same file for an unpublished report.

#### Scenario: A cross-tab with a hidden group
- **WHEN** the CSV of a cross-tab with one respondent in a pair is downloaded, K = 3
- **THEN** that cell reads "<3", its row and column totals read "—", and no cell holds 1

#### Scenario: A grid map
- **WHEN** the CSV of a map block showing squares is downloaded
- **THEN** it lists cell bounds with respondent counts and no point of an answer

#### Scenario: A text block
- **WHEN** the CSV of a text block is requested
- **THEN** the answer is 404

#### Scenario: An unpublished report
- **WHEN** an anonymous visitor asks for a block's CSV of an unpublished report, and its editor asks through the editor
- **THEN** the visitor gets 404 and the editor gets the file

### Requirement: A block downloads as a picture
The system SHALL give an editor a chart, cross-tab, engagement, budget or map block as a PNG with
the block's title, drawn from the block's payload.

#### Scenario: A chart as PNG
- **WHEN** an editor downloads a chart block as PNG
- **THEN** the answer is a PNG image

### Requirement: Every chart and map comes in one archive, made on the worker
The system SHALL build, as a background job like the PDF, a ZIP holding the CSV and the PNG of
every block that has them, numbered in the report's order.

#### Scenario: The archive
- **WHEN** an editor asks for the ZIP of a report with a chart, a text and a map
- **THEN** the job, once run, serves a ZIP with a CSV and a PNG for the chart and for the map and nothing for the text
