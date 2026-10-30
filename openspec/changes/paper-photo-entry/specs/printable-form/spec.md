# printable-form — delta for paper-photo-entry

## MODIFIED Requirements

### Requirement: A printed form is recorded and reused
Printing SHALL write a `PrintedForm` row — canonical survey, `version_number`, `language`,
`paper`, `structure_hash` (sha256 over the rendered items' codes, types, option codes and
wording), `pages`, `layout` (per page: `items`, the keys `section:<code>`, `group:<code>` and
`question:<code>` of every item whose block starts on that page, in drawing order; and for a page
with a frame, `map`: the frame's rectangle on the page in mm, the geographic bounds `[w, s, e, n]`,
zoom, basemap, section code), `tracked_link`, `created_by`, `created_at`. A print whose (survey,
version, language, paper, structure_hash) matches an existing row SHALL reuse it and its code. The
row SHALL survive the deletion of the user that printed it. A row written before `items` existed
SHALL be read with no item map (consumers fall back to the whole structure).

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
