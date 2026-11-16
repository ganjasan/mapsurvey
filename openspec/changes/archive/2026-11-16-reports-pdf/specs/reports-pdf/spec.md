## ADDED Requirements

### Requirement: A report is laid out as an A4 document from the page's own numbers
The system SHALL produce a PDF of a report from the same payload its page renders — the live
aggregates, or the snapshot of a frozen report — containing the opening and every visible block in
order, with the report's address and the page number in the footer of every page. It SHALL count
nothing itself, and a masked count SHALL read as on the page.

#### Scenario: The numbers equal the page
- **WHEN** a frozen report with a live number, a chart and a cross-tab is rendered after more answers arrived
- **THEN** the PDF's text holds the numbers of the snapshot, as the page does

#### Scenario: A masked cell
- **WHEN** the cross-tab has a group under K
- **THEN** the PDF reads "<3" there and nowhere holds the hidden number as that cell

#### Scenario: Every block kind
- **WHEN** a report holds a heading, text with a list, key numbers, quotes, a picture, a chart, an engagement block, a cross-tab and a map
- **THEN** the PDF is produced and its text holds the heading, the list items, the numbers, the quotes and the address

#### Scenario: Hidden blocks stay out
- **WHEN** a report has a hidden text block
- **THEN** the PDF does not hold its text

### Requirement: A map is drawn without a browser
The system SHALL draw a map block as a picture of its cells — or of its marks when the author
chose marks — over the basemap of their extent, and SHALL still produce the PDF, with the cells on
a plain ground, when the basemap cannot be fetched.

#### Scenario: No basemap service
- **WHEN** the basemap cannot be fetched
- **THEN** the PDF is produced with a picture for the map

### Requirement: The PDF is rendered on the worker
The system SHALL render a report's PDF in a background task: asking for one SHALL create a job and
return at once, and the file SHALL be stored on the private media tier when the task has run. A
task delivered twice for the same job SHALL render once.

#### Scenario: Asking returns a job
- **WHEN** an editor asks for the PDF of a 20-block report
- **THEN** the answer names a queued job and no PDF was rendered in that request

#### Scenario: The job finishes
- **WHEN** the worker has run the task
- **THEN** the job is done, and its download serves a PDF to the editor

#### Scenario: Delivered twice
- **WHEN** the same task message arrives again
- **THEN** nothing is rendered a second time

#### Scenario: A failure is reported
- **WHEN** rendering raises
- **THEN** the job is failed and the editor is told the PDF could not be made

### Requirement: A frozen report's PDF is made once and offered on its page
The system SHALL reuse the stored PDF of a frozen report's snapshot for every later request, SHALL
link it from the published report's page, and SHALL serve it to whoever may open that page. A live
report SHALL get a new rendering on every request and no link on its page.

#### Scenario: Rendered once
- **WHEN** an editor asks twice for the PDF of the same frozen report
- **THEN** both answers name the same job

#### Scenario: The link on the page
- **WHEN** a published, frozen report has a stored PDF
- **THEN** its page links to the PDF and the link serves the file to an anonymous visitor

#### Scenario: A live report
- **WHEN** a published live report's PDF was made
- **THEN** its page has no PDF link and the public PDF address answers 404

#### Scenario: A workspace-only report
- **WHEN** an anonymous visitor asks for the PDF of a workspace-only frozen report
- **THEN** they are sent to sign in

### Requirement: Only editors ask for a PDF
The system SHALL let members who may edit a report ask for its PDF and download a job's file, and
SHALL answer 404 to anyone else.

#### Scenario: A stranger
- **WHEN** a member of another workspace posts to the report's PDF address
- **THEN** the answer is 404 and no job is created
