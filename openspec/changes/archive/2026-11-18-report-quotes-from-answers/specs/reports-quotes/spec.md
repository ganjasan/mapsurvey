## ADDED Requirements

### Requirement: The author picks quotes from the answers
The Quotes block's settings SHALL list the answers to the free-text questions (`text`,
`text_line`) of one survey — the report's home survey by default, or another survey of the
workspace the member sees — from clean sessions of the survey and all its versions, filtered by
question and by words the author types, answers of a readable length (30–320 characters) first,
newest first within each, at most 50 at a time with the number found. Adding an answer SHALL append
it to the block as a quote with the question's name as its source, and SHALL keep the survey and
the question's code with it. An answer already in the block SHALL be shown as added.

#### Scenario: Picking an answer
- **WHEN** an author opens a Quotes block of a report whose survey has three answers to "What would you change?" and adds the second
- **THEN** the block holds that answer as a quote with "What would you change?" under it, and the list shows it as added

#### Scenario: Moderated and trashed sessions
- **WHEN** an answer belongs to a session that is trashed or not approved
- **THEN** it is not listed

#### Scenario: A survey the member does not see
- **WHEN** the request names a survey of another workspace or one the member does not see
- **THEN** no answer is listed

### Requirement: A picked quote says where it comes from
A quote added from the answers SHALL keep `ref = {survey, question}`. On every save the system
SHALL mark it `shortened` when its text, with white space collapsed, is not one of that question's
answers in clean sessions. The canvas SHALL label a picked quote "From answers" and a shortened one
"Shortened"; a quote written by hand SHALL carry no label. Readers SHALL see neither label.

#### Scenario: The author trims a picked quote
- **WHEN** an author deletes the last sentence of a picked quote
- **THEN** the saved quote is marked shortened and the canvas says so

### Requirement: The quotes are laid out as the author chooses
A Quotes block SHALL have a layout — `list` (default), `pull` (each quote large, one per row) or
`cards` (two columns on a wide screen, one on a phone) — chosen in its settings and applied on the
report's page, in an embed and on the canvas.

#### Scenario: Cards
- **WHEN** an author sets a Quotes block with four quotes to cards
- **THEN** the page shows them two by two on a computer and one under another on a phone

### Requirement: Quotes that carry contact details are named before publishing
The system SHALL find in a visible quote an email address, a phone number (seven or more numerals,
with spaces, dots, dashes and brackets allowed between them) or a web address, SHALL list those
quotes in their own item of "Before you publish" with a link that opens the block, and SHALL mark
those rows on the canvas. The item SHALL not by itself hold a publication back.

#### Scenario: A phone number in a quote
- **WHEN** a visible quote reads "Call me on +44 7700 900123 about the bench"
- **THEN** "Before you publish" lists it as carrying contact details, and the canvas marks the row

### Requirement: The quotes are edited in place
On the canvas a quote's marks SHALL show only around written text, the button that removes a quote
SHALL be quiet until the row is hovered or focused, and the quotes SHALL be reordered by dragging
a handle, the new order saved at once.

#### Scenario: Reordering
- **WHEN** an author drags the third quote above the first
- **THEN** the block is saved with that order and the page shows it
