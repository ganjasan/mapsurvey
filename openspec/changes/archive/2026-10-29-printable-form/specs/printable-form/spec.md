# printable-form

The paper form of a survey (change printable-form, #489; epic #350 item 2): a PDF built from the
survey's structure, with the section map, a marker legend, a form code and alignment marks.

## ADDED Requirements

### Requirement: A form is printed from the Share page for any status
The Share page SHALL offer **Print a paper form** to members with the `editor` role or above, on
every plan and for every survey status: a language (the survey's languages; one select only when
there is more than one), a paper size (`a4` or `letter`) and a download that answers
`application/pdf` from `GET /editor/surveys/<uuid>/print/form/?lang=<code>&paper=<size>`. A survey
in `draft` or `testing` SHALL print with a diagonal "DRAFT — not for distribution" watermark on
every page; `published` and `closed` SHALL print without it. An unknown language or paper SHALL
answer 400.

#### Scenario: Three clicks from Share
- **WHEN** an editor opens Share of a published two-language survey, picks `pl` and A4 and presses Download PDF
- **THEN** the response is a PDF whose text is the survey's Polish wording

#### Scenario: Viewer cannot print
- **WHEN** a viewer requests the download URL
- **THEN** the response is 403

#### Scenario: Draft watermark
- **WHEN** a draft survey is printed
- **THEN** every page carries the DRAFT watermark text

#### Scenario: Closed survey prints clean
- **WHEN** a closed survey is printed
- **THEN** no page carries the watermark

### Requirement: The form is the respondent survey, built at print time
The PDF SHALL be built from the survey's structure at request time for the `respondent` surface:
sections in chain order, groups as titled blocks with their description, questions in order with
their name and help text in the chosen language. Items whose effective audience excludes
respondents SHALL NOT print. An item with a visibility rule SHALL print with a line "Answer only
if <controller> = <options>" (or "… answered") from the rule's description; a broken rule prints no
line. No structure or text SHALL be stored for the form apart from the `PrintedForm` record.

#### Scenario: Order and translations
- **GIVEN** a survey with two sections, a group and ten questions translated to `de`
- **WHEN** the form is printed in `de`
- **THEN** the text of the PDF contains the German titles, question names and option names in respondent order

#### Scenario: Operator-only items are absent
- **GIVEN** an `operators` section and an `operators` question in an `everyone` section
- **WHEN** the form is printed
- **THEN** neither the section's nor the question's name is in the PDF

#### Scenario: Conditional question prints its condition
- **GIVEN** question HOW shown only when ALB = Yes
- **WHEN** the form is printed
- **THEN** HOW is on the form with the line "Answer only if Albino? = Yes"

#### Scenario: Wording edit changes the form
- **WHEN** a question's name is edited on a live survey and the form is printed again
- **THEN** the new wording is on the form and the form code differs from the previous print's

### Requirement: Every question type has a paper shape
Each `input_type` SHALL render through one entry of `QUESTION_SHAPES`: `text` → four ruled lines,
`text_line` → one line, `number` → a row of boxes, `choice`/`multichoice` → one checkbox per option
in option order with "(choose one)" / "(choose all that apply)" and a write-in line for an "Other"
option, `range` → the numbered scale from the question's bounds, `rating` → the star count as
numbered boxes, `thumbs` → two boxes, `datetime` → a date-and-time field, `ranking` → the options
with a blank in front of each ("write 1 … N"), `html` → the block's text, `image` → the picture,
`photo`/`audio`/`document` → the name and "Online only". A `required` question SHALL carry the
asterisk the respondent page shows. An unknown type SHALL print its name and four lines, never
nothing.

#### Scenario: Choice with write-in
- **GIVEN** a choice question with options Yes, No and Other (write-in)
- **WHEN** the form is printed
- **THEN** the PDF has three boxes and a line after "Other"

#### Scenario: File question
- **GIVEN** a photo question
- **WHEN** the form is printed
- **THEN** its name is on the form followed by "Online only" and no answer box

#### Scenario: Unknown type fails open
- **GIVEN** a question whose `input_type` is not in `QUESTION_SHAPES`
- **WHEN** the form is printed
- **THEN** its name is on the form and the build does not raise

### Requirement: A map section prints its map with layers and a legend
A section of `map` layout that holds at least one geo or Objects-on-the-map question SHALL print
a map frame: a static basemap image at the section's start position, zoom and basemap (else the
survey's; else the bounds of the survey's reference layers; else world), the survey's reference
layers drawn on it in their style with their labels, a scale bar, attribution text under the
frame and a 10 mm white margin inside it. Below the frame a **legend** SHALL list every geo
question of the section with a letter (A, B, … in question order), a symbol by type (point ●,
line ━, area ▭, spray ░), the question's name and the allowed count from its validation settings.
Sub-questions of a geo question SHALL print as a table under the legend whose rows are marks
(A1 … An, n = `max_features` else 3) and whose columns are the sub-questions. An Objects-on-the-map
question SHALL print the layer's objects (title, key) as rows with its sub-questions as columns,
at most 60 rows and a note when cut. A `form`-layout section, or a map section without geo
questions, SHALL print no frame.

#### Scenario: Point question on a map section
- **GIVEN** a map section at Berlin zoom 13 with a point question "Where?" (max 3) and a reference layer "Parks"
- **WHEN** the form is printed
- **THEN** the page has an image frame, the legend reads "A ● Where? — up to 3", the attribution line is present and the layer's objects were drawn

#### Scenario: Sub-questions table
- **GIVEN** the point question has sub-questions "Why?" (text) and "Type" (choice)
- **WHEN** the form is printed
- **THEN** a table with rows A1, A2, A3 and columns Why?, Type follows the legend

#### Scenario: Form section prints no map
- **GIVEN** a section of `form` layout with a point question
- **WHEN** the form is printed
- **THEN** no map frame is on its page and the legend still names the question

#### Scenario: Basemap choice
- **GIVEN** a section with `override_basemap='topo'`
- **WHEN** the map is rendered
- **THEN** the Static Images request names the outdoors style

### Requirement: The map image degrades without a basemap
The frame SHALL print as an empty box with a 10 mm grid and the text "Map unavailable — attach a
printed map here" when `MAPBOX_ACCESS_TOKEN` is empty, the Static Images request fails or it
exceeds 5 seconds; the layers SHALL still be drawn when a position is known, the `PrintedForm`
layout entry SHALL record `basemap: null`, and the view SHALL still answer the PDF. Successful
images SHALL be cached for 24 hours by style, centre, zoom and size.

#### Scenario: No token
- **GIVEN** an empty Mapbox token
- **WHEN** a map section is printed
- **THEN** the PDF is returned, the frame text says the map is unavailable and the layout records a null basemap

#### Scenario: Cached second print
- **WHEN** the same frame is printed twice within a day
- **THEN** the Static Images API is called once

### Requirement: Every page carries alignment marks and a form code
Every page SHALL carry four filled black 6 × 6 mm squares 8 mm from its corners, a footer with the
form code as text `MS-<form>-<page>` and "page N of M", and a 16 mm QR whose payload is
`ms:form:<form>:<page>:<pages>`. The code SHALL name a `PrintedForm` row, never the survey's uuid.
Page 1 SHALL additionally carry a QR with the survey's online link through a `TrackedLink`
(`utm_source='paper'`, `utm_medium='print_form'`, created on first print and reused) and an
"Office use — sheet no." box.

#### Scenario: Marks and code on every page
- **GIVEN** a form of three pages
- **WHEN** the PDF is read back
- **THEN** each page has four squares at the corners and a footer code ending in that page's number

#### Scenario: Code does not leak the survey key
- **WHEN** the QR payloads are decoded
- **THEN** none contains the survey uuid or a public URL except the page-1 online-link QR

#### Scenario: Tracked link reused
- **WHEN** the same survey is printed twice
- **THEN** one `TrackedLink` with `utm_source='paper'` exists for it

### Requirement: A printed form is recorded and reused
Printing SHALL write a `PrintedForm` row — canonical survey, `version_number`, `language`,
`paper`, `structure_hash` (sha256 over the rendered items' codes, types, option codes and
wording), `pages`, `layout` (per page with a frame: the frame's rectangle on the page in mm, the
geographic bounds `[w, s, e, n]`, zoom, basemap, section code), `tracked_link`, `created_by`,
`created_at`. A print whose (survey, version, language, paper, structure_hash) matches an
existing row SHALL reuse it and its code. The row SHALL survive the deletion of the user that
printed it.

#### Scenario: Reprint keeps the code
- **WHEN** the same unchanged survey is printed twice in the same language and paper
- **THEN** one `PrintedForm` exists and both PDFs carry its code

#### Scenario: Layout records the frame
- **GIVEN** a map section printed on page 2
- **WHEN** the row is read
- **THEN** `layout["2"]["map"]` has the rectangle in mm, the bounds, the zoom and the section code

#### Scenario: Structural change makes a new form
- **WHEN** a question is added through unpublished changes and published, and the form is printed again
- **THEN** a second `PrintedForm` with a higher `version_number` exists

### Requirement: Printing is a creator event
The view SHALL emit `form_printed` with `survey_id`, `paper`, `language`, `pages` and `map_pages`
and nothing else.

#### Scenario: Event payload
- **WHEN** a form is downloaded
- **THEN** one `form_printed` event is emitted with those five properties and no URL

### Requirement: Fixed form strings are in the form's language
The form's fixed strings SHALL be rendered through the respondent catalogs in the form's language
("Answer only if", "choose one", "Online only", "Mark on the map", "Office use", "page N of M",
"Map unavailable …"), and the respondent catalog completeness test SHALL cover them.

#### Scenario: Polish form
- **WHEN** a form is printed in `pl`
- **THEN** its fixed strings are Polish
