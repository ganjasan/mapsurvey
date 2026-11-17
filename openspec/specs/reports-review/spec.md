# reports-review Specification

## Purpose
Review before a report goes out: the "Before you publish" list (what names or places people, what looks unfinished, each with a fix), the confirmation that quotes and maps of marks were read, the publish dialog with audience and live-or-frozen, map descriptions and the two preview widths. Implementation: `reports/checks.py`, `reports/services.py`, `reports/editor_views.py`; tests `survey/tests/test_reports_review.py`.
## Requirements
### Requirement: The author sees what a report says about people before publishing
The system SHALL show, when an editor asks to publish a report, every quote of its visible Quotes
blocks written out, every map block that shows individual marks, and a warning when the threshold
is 1. Hidden blocks SHALL not be listed.

#### Scenario: Picked quotes are named
- **WHEN** a report has a visible Quotes block with two quotes and a hidden one with three
- **THEN** the list writes out the two quotes and none of the three

#### Scenario: A map of marks
- **WHEN** a map block shows marks
- **THEN** the list names that block and says a mark can point at someone's home

#### Scenario: Nothing to check
- **WHEN** a report has only headings, text and charts with the threshold at 3
- **THEN** the dialog says there is nothing to check

### Requirement: Quotes and marks are published only after a confirmation
The system SHALL refuse to publish a report that has a visible quote or a map of marks unless the
editor confirmed having read them, and SHALL publish any other report without a confirmation.
Taking a report down SHALL never need one.

#### Scenario: Without the confirmation
- **WHEN** an editor publishes a report with a visible quote and does not tick the confirmation
- **THEN** the report stays unpublished and the dialog says what is missing

#### Scenario: With the confirmation
- **WHEN** the editor ticks it and publishes
- **THEN** the report is published

#### Scenario: A report without quotes or marks
- **WHEN** an editor publishes a report of charts and text
- **THEN** it is published without a confirmation

### Requirement: The dialog names what looks unfinished and offers the fix
The system SHALL list a visible block that renders nothing with a button that deletes it, a map
block without a description with a link that opens it, a missing title with a link to the settings,
and the number of hidden blocks; none of these SHALL hold a publication back.

#### Scenario: An empty block
- **WHEN** a report has a visible Quotes block with no quote
- **THEN** the list offers to delete it, and deleting it removes the item from the list

#### Scenario: A map nobody described
- **WHEN** a map block has no description
- **THEN** the list says so and links to the block, and the report can still be published

### Requirement: Publishing chooses audience and numbers
The system SHALL let the editor choose, in the same dialog, who can open the report (public,
unlisted, workspace only) and whether its numbers are live or frozen as they are now, and SHALL
apply both with the publication.

#### Scenario: Frozen and unlisted
- **WHEN** an editor publishes choosing "unlisted" and "frozen"
- **THEN** the report is published, unlisted, and shows the numbers of that moment after new answers arrive

### Requirement: A map says what it shows
The system SHALL let an editor give a map block one sentence that is shown under the map and
exposed to assistive technology as the map's description.

#### Scenario: Described
- **WHEN** a map block's description is "Most marks sit along the river path"
- **THEN** the page shows the sentence under the map and the map carries it as its accessible name

### Requirement: The preview shows a phone or a computer
The system SHALL let the editor switch the editor's preview pane between a phone's width and a
computer's.

#### Scenario: The two widths
- **WHEN** the editor page is rendered
- **THEN** the preview pane offers "as on a phone" and "as on a computer"

