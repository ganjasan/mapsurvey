## MODIFIED Requirements

### Requirement: A block's primary actions happen in the block
In the builder, the control that makes a block what it is SHALL be inside the block on the canvas, and the Settings panel SHALL hold only secondary options. Primary, in the block: the picture of an image block (drop zone, choose, replace), the link of a video block, the link of a button block, the files of a documents block (add, rename, remove), the area of a map block (drop zone, replace), the questions and answers of an FAQ block (edit, add, remove), the phases of a timeline block (edit, add, remove, mark Now), the survey of an empty survey card, the question of an empty results block, the date, start, end and place of an event block, and the cover picture of the page head (choose, drop, replace, remove). Secondary, in Settings: picture description (of a block and of the cover), button style, map colour and base map, chart style, a card's or a results block's change of survey or question, time zone, seats, the registration switch and the attendee list. No block SHALL tell the creator to go to the settings to fill it in. The values SHALL be saved through the same block form and validation as before.

#### Scenario: Empty image block
- **WHEN** an editor adds an Image block
- **THEN** the block shows a drop zone with a "choose a file" control and no text pointing to the settings

#### Scenario: FAQ edited in place
- **WHEN** the builder renders an FAQ block with two questions
- **THEN** both questions and answers are editable in the block, with a remove control per row and an "Add a question" control

#### Scenario: A row still being written
- **WHEN** the builder autosaves an FAQ row whose answer is typed before its question
- **THEN** the row is kept without an error, and the public page draws only the rows that have a question

#### Scenario: Secondary option in Settings
- **WHEN** the builder renders a map block's settings
- **THEN** the panel offers the colour and the base map and no GeoJSON upload

#### Scenario: Cover picture on the page head
- **WHEN** an editor presses "Add a cover picture" on the page head, or drops a picture onto it
- **THEN** the file chooser opens (or the dropped picture is taken), the cover is saved at once and shown, and a remove control appears beside "Change the cover picture"
