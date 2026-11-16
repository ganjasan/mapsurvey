## ADDED Requirements

### Requirement: Writing a report needs the Reports feature
The system SHALL let a member create a report, add, change, reorder or delete a block, change a
report's settings, publish it, import one or copy one only when the report's workspace has the
`reports` feature by its plan or by a live Pro trial, or when that write starts the workspace's
trial. Otherwise the write SHALL be refused with the upgrade page and SHALL change nothing.

#### Scenario: A Pro workspace
- **WHEN** an editor of a Pro workspace adds a block
- **THEN** the block is added

#### Scenario: The first write starts the trial
- **WHEN** an editor of a workspace that never had a trial adds a block
- **THEN** the block is added and the workspace has a live trial that includes Reports

#### Scenario: After the trial
- **WHEN** an editor of a free workspace whose trial has ended adds a block, publishes or creates a report
- **THEN** each is refused with the upgrade page and nothing changes

### Requirement: The editor opens read-only without the feature
The system SHALL open a report's editor for a member of a workspace without the feature, show that
the report is read-only and where to upgrade, and SHALL keep export and the PDF available. Nothing
SHALL be deleted.

#### Scenario: A lapsed workspace opens its report
- **WHEN** an editor of a workspace whose subscription lapsed opens a report
- **THEN** the page opens, says the report is read-only on the current plan, links to the plan page, and lists the blocks

#### Scenario: Export still works
- **WHEN** that editor exports the report
- **THEN** the report file downloads

### Requirement: A report of a workspace without the feature is served frozen
The system SHALL serve a published report whose workspace lacks the feature as a frozen snapshot at
its unchanged address: a live report SHALL be frozen as it stands the first time it is requested
after the cover ended, and SHALL then keep those numbers. The page SHALL never answer 404 or an
upgrade page for the plan. A covered workspace's live report SHALL stay live.

#### Scenario: A free workspace's published page
- **WHEN** a published live report of a free workspace is requested, and a new answer arrives, and it is requested again
- **THEN** both responses are 200 at the same address, the report is frozen, and the second shows the first's numbers

#### Scenario: A lapsed subscription
- **WHEN** a Pro workspace's subscription ends and its published live report is requested
- **THEN** the page opens with a "Data as of" date and the report is frozen

#### Scenario: A Pro workspace stays live
- **WHEN** a Pro workspace's published live report is requested twice with a new answer in between
- **THEN** the second response shows the new number

#### Scenario: A block's page and its CSV
- **WHEN** a block's own page or CSV of a free workspace's published live report is requested
- **THEN** the report is frozen and the response is served from the snapshot

### Requirement: Affected reports can be counted and frozen at once
The system SHALL provide a command that lists the published live reports of workspaces without the
feature and, unless run dry, freezes them.

#### Scenario: Dry run
- **WHEN** the command runs with --dry-run over one free and one Pro workspace's published reports
- **THEN** it names the free workspace's report only and changes nothing

#### Scenario: Freezing
- **WHEN** the command runs without --dry-run
- **THEN** the free workspace's report is frozen and the Pro workspace's is not
