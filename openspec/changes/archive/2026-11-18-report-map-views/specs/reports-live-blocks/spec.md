## MODIFIED Requirements

### Requirement: The author of a report may show the marks of a map block
The system SHALL build a map block from areas that count respondents unless the report's editor
switched "Use every mark" on for that block; then the block SHALL carry the geometry of every mark
of clean, non-empty sessions and nothing else — no identifier, no session, no answer to a
sub-question. Picking the Marks view SHALL switch it on, and switching it off while the marks are
shown SHALL return the block to a view built from areas.

#### Scenario: Off by default
- **WHEN** a map block is added
- **THEN** its page payload holds cells and no mark

#### Scenario: Switched on
- **WHEN** an editor switches the marks on for a block of a point question with 5 points
- **THEN** the page payload holds 5 point geometries with empty properties, and no cell

#### Scenario: Switched off again
- **WHEN** the editor switches it off
- **THEN** the payload holds cells again

#### Scenario: The Marks view
- **WHEN** an editor picks the Marks view of a block whose switch is off
- **THEN** the payload holds every mark, and publishing the report asks the author to confirm

## ADDED Requirements

### Requirement: A map block is drawn the way its author chooses
A map block SHALL be drawn as one of `heat` (shading, darker where more people marked), `hotspots`
(a point question's numbered places, largest first, listed under the map with their respondents and
marks), `squares` or `marks`. A new block SHALL start as heat; a block without display settings
SHALL stay squares, or marks when its switch was on. A hot spot SHALL hold at least two marks and at
least K distinct respondents, or two marks alone when the author uses every mark; places below that
SHALL appear nowhere in the payload unless the author uses every mark. Hot spots SHALL be computed
by the Data module. The page, the PDF, the PNG and the CSV SHALL draw the same payload, and the
report file SHALL carry the view.

#### Scenario: A new map
- **WHEN** an editor adds the map block of a point question
- **THEN** it is drawn as heat from cells that count respondents

#### Scenario: Hot spots under K
- **WHEN** three people marked one corner, one person another place, K is 3 and the editor picks Hot spots
- **THEN** one spot is numbered with 3 respondents and 3 marks, and the lone mark is not in the payload

#### Scenario: Hot spots of every mark
- **WHEN** two people marked a third place and the editor switches "Use every mark" on
- **THEN** that place is numbered too

#### Scenario: A line question
- **WHEN** Hot spots is asked for the map of a line question
- **THEN** the block is drawn as heat

#### Scenario: A block made before
- **WHEN** a map block has no display settings
- **THEN** it is drawn as squares

#### Scenario: A copy of the report
- **WHEN** a report with a map drawn as hot spots is copied
- **THEN** the copy's map is drawn as hot spots

### Requirement: The author frames a map block
The editor SHALL be able to keep the part of the map shown on the canvas as the block's frame, and
to clear it; a block with a frame SHALL open on that part for readers and in the PDF, and a block
without one on everything there is to draw. A frame that is not a west–south–east–north box SHALL be
ignored.

#### Scenario: Keeping a view
- **WHEN** the editor keeps a view of the map
- **THEN** the block's payload carries that frame and a copy of the report keeps it

#### Scenario: Clearing it
- **WHEN** the editor chooses to show all the answers
- **THEN** the payload carries no frame

#### Scenario: Nonsense
- **WHEN** a frame whose east is west of its west is posted
- **THEN** the block has no frame
