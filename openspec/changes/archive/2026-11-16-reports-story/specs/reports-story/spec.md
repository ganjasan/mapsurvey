## ADDED Requirements

### Requirement: A report is a linear story
The system SHALL render a report as one column in the order of its blocks: an opening (an optional
line above the title, the title, an opening paragraph), then headings, text, pictures, key numbers,
quotes, charts and maps as the author arranged them. Two consecutive half-width blocks SHALL share
a row on a wide screen and stack on a narrow one.

#### Scenario: The opening
- **WHEN** a report has the line "Neighbourhood plan · survey report", a title and an opening paragraph
- **THEN** its page shows the line above the title and the paragraph under it

#### Scenario: Two half-width blocks
- **WHEN** two consecutive blocks are half width and the next one is full width
- **THEN** the page puts the two in one row and the third in a row of its own

#### Scenario: A lone half-width block
- **WHEN** a half-width block is followed by a full-width one
- **THEN** each has its own row

### Requirement: The author writes headings, text, key numbers and quotes
The system SHALL offer the block types Heading, Text, Image, Key numbers and Quotes beside the
blocks that show a question. Text SHALL be rich text sanitised by the creator allow-list. Key
numbers SHALL be values with labels typed by the author; quotes SHALL be texts with an optional
source line typed or pasted by the author. A block with nothing in it SHALL not appear on the page.

#### Scenario: Key numbers
- **WHEN** an author enters "447 | residents answered" and "1,921 | places pinned" in a Key numbers block
- **THEN** the page shows 447 with "residents answered" and 1,921 with "places pinned"

#### Scenario: A quote with its source
- **WHEN** an author enters "Give us the bridge back. | Pin: needs attention" in a Quotes block
- **THEN** the page shows the quote and, under it, "Pin: needs attention"

#### Scenario: Script in a text block
- **WHEN** a Text block is saved with a script element and a bold word
- **THEN** the page keeps the bold word and carries no script

#### Scenario: An empty block
- **WHEN** a Quotes block has no quote
- **THEN** the page does not show it

#### Scenario: A page frozen before text was rich
- **WHEN** a frozen snapshot holds a text block written as plain text with an angle bracket in it
- **THEN** the page shows that text escaped
