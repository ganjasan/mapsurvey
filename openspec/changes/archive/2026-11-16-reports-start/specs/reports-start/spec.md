## ADDED Requirements

### Requirement: A report starts from a card
The system SHALL offer an editor of a workspace a start page whose cards each create a report on one
click and open it in the editor: a draft from a chosen survey in one of the arrangements, a blank
report, and a copy of a report the member may see. Members who may not edit SHALL not reach it.

#### Scenario: One click drafts a report
- **WHEN** an editor presses the "Consultation summary" card with a survey chosen
- **THEN** a new unpublished report of that survey exists and its editor opens

#### Scenario: A blank report
- **WHEN** an editor presses "Blank report"
- **THEN** an unpublished report without a home survey opens in the editor

#### Scenario: A viewer
- **WHEN** a viewer opens the start page
- **THEN** the answer is 404

#### Scenario: No survey to draft from
- **WHEN** the workspace has no published survey
- **THEN** the page offers the blank report and says why no draft is offered

### Requirement: The draft is built by rules from what people answered
The system SHALL build a draft without a language model: an opening with the number of people who
answered as a live number, key numbers and the engagement block first, then one block for every
top-level question that has at least one answer in clean sessions, in the survey's order — a chart
for choice, rating and number questions, a map for map questions — with the survey's section titles
as headings when it has more than one section. A question without answers SHALL get no block. The
survey's first report SHALL be left unchanged.

#### Scenario: A block for every answered question
- **WHEN** a survey has an answered choice question, an answered map question and a choice question nobody answered
- **THEN** the draft holds a chart for the first, a map for the second and nothing for the third

#### Scenario: Who took part comes first
- **WHEN** a draft is made
- **THEN** its first data block is the engagement block

#### Scenario: The survey's own report stays
- **WHEN** a draft is made from a survey that already has a report
- **THEN** that report keeps its blocks and a second report exists

### Requirement: Nothing unfinished reaches a visitor
The system SHALL create a draft unpublished; SHALL add answers to free-text questions as a Quotes
block that is hidden until the author shows it, holding at most eight recent answers of readable
length from clean sessions; and SHALL add the text the author is asked to write as hidden blocks.

#### Scenario: Quotes to pick from
- **WHEN** a survey has a free-text question with answers and a draft is made and published as it is
- **THEN** the report's page shows none of those answers

#### Scenario: Prompts are hidden
- **WHEN** a draft is published as it is
- **THEN** the page shows no prompt such as "Write what this part of the survey showed"

### Requirement: A draft comes in four arrangements
The system SHALL arrange the same draft as a Consultation summary, a Council paper (numbered
sections, choice results as tables), an Engagement update (key numbers, engagement and maps only,
with the link to take part) or You said — we did (each result under a "You said" heading, followed
by a hidden place for what was done), and each SHALL produce a report whose page renders.

#### Scenario: Every arrangement renders
- **WHEN** each of the four arrangements is made from the same survey
- **THEN** each report's preview opens and shows at least one block

#### Scenario: The council paper uses tables
- **WHEN** the Council paper is made
- **THEN** its headings are numbered and its choice blocks are tables

### Requirement: A report can be copied
The system SHALL create, from a report the member may see, a second report with the same opening
and blocks, titled as a copy, unpublished and visible to the workspace only.

#### Scenario: Copying
- **WHEN** an editor copies a published report with five blocks
- **THEN** a second report with the same five blocks exists, unpublished, and the first is unchanged

### Requirement: A report can be started where the data is
The system SHALL link to the start page with the survey chosen from the Responses page of a
published survey and from that survey's responses dataset, for members who may edit.

#### Scenario: From Responses
- **WHEN** an editor opens the Responses page of a published survey
- **THEN** the page offers "Make a report" leading to the start page with that survey chosen
