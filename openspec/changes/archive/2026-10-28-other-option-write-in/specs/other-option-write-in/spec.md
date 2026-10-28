## ADDED Requirements

### Requirement: A choice question designates at most one write-in option
A `choice` or `multichoice` question MAY mark one option as its write-in option by storing `"other": true` on that option's object in `Question.choices`. Every path that saves choices (question create, edit, autosave, sub-question create, live preview) SHALL keep the flag on the first flagged option and remove it from any others. `Question.other_choice_code()` SHALL return that option's code, or `None`. The flag SHALL have no effect on `rating`, `range`, `ranking` and `thumbs` questions.

#### Scenario: One option is flagged
- **WHEN** a creator saves a choice question whose option with code 4 carries `other: true`
- **THEN** `question.other_choice_code()` returns 4 and the other options carry no flag

#### Scenario: Two flags collapse to one
- **WHEN** a save arrives with `other: true` on codes 2 and 4
- **THEN** the stored choices carry the flag on code 2 only

#### Scenario: Flag on a rating question is inert
- **WHEN** a rating question's stored choices carry `other: true` on one option
- **THEN** the respondent form renders no write-in field and `other_choice_code()` is used by no path

### Requirement: The write-in field follows the option on every surface
Wherever a question with a write-in option renders — a section card, the dropdown display style, a sub-question form inside a geo feature popup, an Objects-on-the-map popup, the editor's live preview — the option's markup SHALL include a text input named `<question code>-other` directly beneath the option. The input SHALL be hidden and disabled unless the flagged option is selected; selecting the option SHALL reveal, enable and focus it; deselecting SHALL hide and disable it again. The state SHALL be recomputed when a popup opens with restored values.

#### Scenario: Selecting the option reveals the field
- **WHEN** a respondent selects the flagged option of a single-choice question
- **THEN** the write-in input under it becomes visible and enabled and receives focus

#### Scenario: Deselecting hides and disables the field
- **WHEN** the respondent then selects a different option
- **THEN** the write-in input is hidden and disabled and is not part of the submitted form

#### Scenario: Multichoice keeps the field while the option stays checked
- **WHEN** a respondent checks the flagged option and two other options of a multichoice question
- **THEN** the write-in input stays visible until the flagged option is unchecked

#### Scenario: A popup restores the field state
- **WHEN** a geo feature whose stored properties include the flagged code and a write-in text is reopened
- **THEN** the popup shows the option checked and the write-in input visible with the stored text

#### Scenario: A hidden write-in does not satisfy the required check
- **WHEN** a required choice question has text left in a hidden write-in input and no option selected
- **THEN** Next reports the question as unanswered

### Requirement: Write-in text is stored on the choice answer
The system SHALL store the write-in text in `Answer.text` of the same row that holds `selected_choices`, at every storage site (section answers, geo sub-answers, object answers), and only when the flagged option's code is among the selected codes. An empty write-in with the option selected SHALL be stored as an empty string. Text posted while the flagged option is not selected SHALL be discarded.

#### Scenario: Top-level answer with write-in
- **WHEN** a section POST carries `Q1=4` and `Q1-other=wet towel` for a question whose write-in option is 4
- **THEN** one Answer row has `selected_choices=[4]` and `text="wet towel"`

#### Scenario: Geo sub-answer with write-in
- **WHEN** a submitted feature's properties carry `S1: ["4"]` and `S1-other: ["graffiti"]`
- **THEN** the child Answer for S1 has `selected_choices=[4]` and `text="graffiti"`, and no Answer is created for `S1-other`

#### Scenario: Object answer with write-in
- **WHEN** the POST carries `obj__k1__S1=4` and `obj__k1__S1-other=broken bench`
- **THEN** the Answer for object k1 and sub-question S1 has `selected_choices=[4]` and `text="broken bench"`

#### Scenario: Text without the option is discarded
- **WHEN** a POST carries `Q1=2` and `Q1-other=stale`
- **THEN** the stored Answer has `selected_choices=[2]` and `text` is null

#### Scenario: Empty write-in is allowed
- **WHEN** a POST carries `Q1=4` and an empty `Q1-other`
- **THEN** the Answer has `selected_choices=[4]` and `text=""`

### Requirement: Exports carry the write-in in an adjacent column
For every question with a write-in option, the CSV export, the GeoJSON feature properties of geo sub-questions and the per-object CSV SHALL contain a column named `"<question name>: <write-in option label>"` next to the question's column, holding the write-in text when the option was selected and an empty string otherwise. The question's own column SHALL keep the option label(s) as before.

#### Scenario: CSV column pair
- **WHEN** a survey with such a question is exported and one session picked the write-in option with text "wet towel" while another picked option 1
- **THEN** the CSV has the columns `"How do you cope?"` and `"How do you cope?: Other (specify)"`, the first row reads `Other (specify)` / `wet towel` and the second `Stay indoors` / empty

#### Scenario: GeoJSON property pair
- **WHEN** a geo feature's sub-answer picked the write-in option
- **THEN** the feature's properties carry both the sub-question's label and the adjacent write-in key

#### Scenario: Multichoice keeps its joined labels
- **WHEN** a multichoice answer selected option 1 and the write-in option with text "mall"
- **THEN** the question column reads `Seek shade; Other (specify)` and the adjacent column reads `mall`

#### Scenario: No write-in option, no extra column
- **WHEN** a choice question has no flagged option
- **THEN** the export contains only its usual column

### Requirement: The creator sees the write-in inline; public surfaces never do
The Responses table, the response drawer and the map attribute lists SHALL show a choice answer with write-in as `"<option label>: <text>"` inline. Aggregate charts SHALL count the write-in option by code like any other option. The public results page and Objects-on-the-map aggregates SHALL carry no write-in text.

#### Scenario: Drawer shows the text
- **WHEN** a creator opens a response whose choice answer selected the write-in option with text "wet towel"
- **THEN** the drawer row reads `Other (specify): wet towel`

#### Scenario: Chart counts by code
- **WHEN** three responses selected the write-in option
- **THEN** the question's chart shows the option's label with count 3 and no text

#### Scenario: Public results carry no text
- **WHEN** the public results page renders a block for that question
- **THEN** the payload contains the option's masked count and no occurrence of any write-in text

#### Scenario: Object aggregates carry no text
- **WHEN** object aggregates are computed for a layer whose sub-question has a write-in option
- **THEN** the counts include the option's code and no write-in text appears in the aggregate
