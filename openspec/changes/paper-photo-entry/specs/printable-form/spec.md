# printable-form — delta for paper-photo-entry

## MODIFIED Requirements

### Requirement: Every page carries alignment marks and a form code
Every page SHALL carry four filled black 6 × 6 mm squares 8 mm from its corners and, in the
footer, a QR in EACH bottom corner (20 mm, error level H, drawn as vector shapes) whose payload is
`MSFORM:<form>:<copy>:<page>:<pages>` (`<copy>` 0 on a form printed without copy numbers), with
the human line `MS-<form> · #<copy> · Page N of M` between them (`MS-<form> · Page N of M`
without copy numbers). A numbered copy SHALL also print `#<copy>` large at the top right of every
page. The code SHALL name a `PrintedForm` row, never the survey's uuid. Page 1 SHALL additionally
carry a QR with the survey's online link through a `TrackedLink` (`utm_source='paper'`,
`utm_medium='print_form'`, created on first print and reused) and an "Office use — sheet no." box.
Payloads of forms printed before copy numbers (`ms:form:<form>:<page>:<pages>`) SHALL still parse.

#### Scenario: Marks and code on every page
- **GIVEN** a form of three pages
- **WHEN** the PDF is read back
- **THEN** each page has four squares at the corners and a footer line ending in "Page N of 3" for its number

#### Scenario: Code does not leak the survey key
- **WHEN** the QR payloads are decoded
- **THEN** none contains the survey uuid or a public URL except the page-1 online-link QR

#### Scenario: Tracked link reused
- **WHEN** the same survey is printed twice
- **THEN** one `TrackedLink` with `utm_source='paper'` exists for it

#### Scenario: Both corners read locally
- **WHEN** a page of a numbered copy is rendered at 200 dpi and decoded with zxing-cpp
- **THEN** the code names the form, the copy, the page and the page count

### Requirement: A printed form is recorded and reused
Printing SHALL write a `PrintedForm` row — canonical survey, `version_number`, `language`,
`paper`, `structure_hash` (sha256 over the rendered items' codes, types, option codes and
wording, and the page-layout version), `pages`, `layout` (per page: `items`, the keys
`section:<code>`, `group:<code>` and `question:<code>` of every item whose block starts on that
page, in drawing order; and for a page with a frame, `map`: the frame's rectangle on the page in mm,
the geographic bounds `[w, s, e, n]`, zoom, basemap, section code), `tracked_link`, `created_by`,
`created_at`. A print whose (survey, version, language, paper, structure_hash) matches an existing
row SHALL reuse it and its code. The row SHALL survive the deletion of the user that printed it. A
row written before `items` existed SHALL be read with no item map (consumers fall back to the whole
structure).

#### Scenario: Reprint keeps the code
- **WHEN** the same unchanged survey is printed twice in the same language and paper
- **THEN** one `PrintedForm` exists and both PDFs carry its code

#### Scenario: Layout records the frame
- **GIVEN** a map section printed on page 2
- **WHEN** the row is read
- **THEN** `layout["2"]["map"]` has the rectangle in mm, the bounds, the zoom and the section code

#### Scenario: Layout records the items of every page
- **GIVEN** a form whose section S2 with questions Q5 and Q6 starts on page 2
- **WHEN** the row is read
- **THEN** `layout["2"]["items"]` contains `section:S2`, `question:Q5` and `question:Q6` in that order and `layout["1"]["items"]` contains none of them

#### Scenario: Structural change makes a new form
- **WHEN** a question is added through unpublished changes and published, and the form is printed again
- **THEN** a second `PrintedForm` with a higher `version_number` exists

## ADDED Requirements

### Requirement: A form prints as numbered copies or as one copy to photocopy
The Share page's *Print a paper form* SHALL offer **Numbered copies** (a number, 1…200, default 20)
and **One copy to photocopy**. `GET …/print/form/?mode=copies&copies=N` SHALL answer one PDF holding
N copies, each with its own copy number on every page; `mode=single` (or no `mode`) SHALL answer
one copy without numbers. Copy numbers SHALL belong to the canonical survey and SHALL only grow:
every print run (`PrintRun`: survey, form, `first_copy`, `last_copy`, `created_by`) continues
after the highest number printed before, whatever its form, version, language or paper, under a
lock on the canonical survey row, so a copy number names exactly one paper questionnaire for the
life of the survey. The form SHALL be laid out once per print; each copy's page SHALL be that
layout plus its own codes (the body stored once in the PDF). A copies count outside 1…200 or an
unknown mode SHALL answer 400 and spend no numbers. The Share page SHALL say how many numbered
copies were printed so far and where the next print starts, and that a photocopy repeats its
number. `form_printed` SHALL carry `copies` (0 for one copy to photocopy).

#### Scenario: Keep each map with its tables on one page
- **GIVEN** the dialog's *Keep each map with its tables on one page* (`?keep=1`, on by default)
- **WHEN** a map section does not fit under the questions above it
- **THEN** its heading, frame, legend and marks tables move to the next page whole instead of the tables being cut in two; the form is its own `PrintedForm` row (`keep` is in the structure hash) and `form_printed` carries `keep_together`

#### Scenario: File questions are not printed
- **WHEN** a survey with a photo question is printed
- **THEN** nothing of it is on the paper: no "Online only" stub, no entry in the page items

#### Scenario: Numbering continues across prints
- **GIVEN** 3 numbered copies printed in English
- **WHEN** 2 more are printed in German
- **THEN** the first PDF holds copies #1–#3, the second #4–#5, and two `PrintRun` rows record the ranges

#### Scenario: Bad count
- **WHEN** 0 or 201 copies, or an unknown mode, are requested
- **THEN** the response is 400 and no `PrintRun` is written

#### Scenario: The body is stored once
- **WHEN** 20 copies of a ten-page form with maps are printed
- **THEN** the PDF is about the size of one copy plus the codes, not twenty times one copy
