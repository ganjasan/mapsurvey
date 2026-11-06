# paper-photo-entry Specification

## Purpose
TBD - created by archiving change paper-photo-entry. Update Purpose after archive.
## Requirements
### Requirement: Paper responses are reached from Responses under the operator entry gate
The Responses page SHALL offer *From photos of paper forms* beside *Type in a response* under
*Enter a response*, to members with the `editor` role or above, gated per request by the Pro
feature `operator_entry` on the organisation that owns the survey (the same gate as the entry
header). The page *Paper responses* SHALL be served at `/editor/surveys/<uuid>/responses/paper/`,
one response at `…/paper/r/<id>/`; a response of another survey SHALL answer 404. Every survey SHALL
have ONE hidden inbox (`PaperBatch`, found or made by `paper.inbox_for`) that numbers uploads, pages
and responses; the operator never sees, opens or closes it.

#### Scenario: Editor of a Pro workspace opens the page
- **WHEN** an `editor` of a Pro organisation clicks *From photos of paper forms*
- **THEN** *Paper responses* renders with *New response* and *Upload a stack*, and one open inbox exists for the canonical survey

#### Scenario: Viewer cannot
- **WHEN** a `viewer` requests the page
- **THEN** the response is 403

#### Scenario: Free workspace sees the refusal
- **WHEN** an `editor` of a Free organisation requests the page
- **THEN** the response is the `require_feature` refusal

#### Scenario: Another survey's response
- **WHEN** an editor requests `…/paper/r/<id>/` with a response of a different survey
- **THEN** the response is 404

### Requirement: The page states what was printed and what came back
*Paper responses* SHALL show, per printed form (newest first), the numbered copies printed and how
many of them have a response; the open responses as cards (label, one slot per page of the form —
missing, being read, read, doubtful, failed — and *Check* / *Skip*); the photos set aside with their
reason; uploads still being split or failed; and the last stored responses. *Check next* SHALL open
the next response to check: complete ones first in order, then incomplete ones holding at least one
read page; with none it SHALL stay on the page. The list SHALL re-render every 3 seconds while an
upload or a page is in flight. A response's label SHALL be "Copy N" for a numbered copy and
"Response N" (its inbox number) otherwise.

#### Scenario: Copies back
- **GIVEN** copies 1–20 printed and responses for copies 3 and 7
- **WHEN** the page renders
- **THEN** it reads 20 printed, 2 back, and shows cards "Copy 3" and "Copy 7"

#### Scenario: Check next prefers complete responses
- **GIVEN** Copy 5 incomplete with one read page and Copy 9 complete
- **WHEN** the operator presses *Check next*
- **THEN** Copy 9 opens

### Requirement: Files upload one per request, into the inbox or into a response
`POST …/paper/upload/` SHALL take exactly one file (multipart `file`) and optionally `sheet` (a
response of this survey that is still open) and `page_number` (what a page whose code will not read
is taken for); it SHALL create a `PaperUpload` with the next inbox `seq`, store the file on the
private media tier under a random `paper_uploads/<uuid>` key without reading its content in the
request, enqueue the ingest task and answer JSON `{id, seq}`. A file over `PAPER_UPLOAD_MAX_BYTES`
(default 40 MB) SHALL answer 413; an inbox holding `PAPER_BATCH_MAX_PAGES` (default 500) images, or
a `sheet` that is stored or skipped, SHALL answer 409. The pages SHALL upload the selected files
one after another with progress per file, keep the drop zone active while earlier files are read,
and offer *Take photo* (the camera, on a phone) next to *choose files*.

#### Scenario: A stack at once
- **WHEN** the operator drops thirty JPEGs on *Upload a stack*
- **THEN** thirty `PaperUpload` rows exist with `seq` 1…30, none tied to a response, and thirty ingest tasks are enqueued

#### Scenario: Into a response
- **WHEN** a photo is posted with `sheet` = Response 4
- **THEN** the upload names Response 4

#### Scenario: File too large
- **WHEN** a 60 MB file is posted
- **THEN** the response is 413 and no `PaperUpload` is created

#### Scenario: Stored response
- **WHEN** a file is posted with the id of a stored response
- **THEN** the response is 409 and nothing is stored

### Requirement: New response makes an empty response to photograph a form into
`POST …/paper/new/` SHALL create an empty `PaperSheet` with the next inbox number and open its
page, where the operator adds photos or a PDF of ONE filled form. It SHALL emit
`paper_response_created` with `surface='new_response'`. An empty response SHALL take the copy
number of the first numbered page placed in it.

#### Scenario: One form by hand
- **WHEN** the operator presses *New response* and adds three photos of a form printed without numbers
- **THEN** one response "Response N" holds the three pages by their page numbers

### Requirement: Ingest splits, converts, normalises and reads the code in the worker
The ingest task SHALL sniff the upload's type from its bytes and accept JPEG, PNG, WEBP, HEIC/HEIF
and PDF; anything else SHALL mark the upload `failed` with "Not a photo or PDF". A PDF SHALL be
rendered page by page at 200 dpi; an image SHALL be EXIF-transposed. The page's form code SHALL be
decoded locally (zxing-cpp) from the full-resolution page, then from enlarged crops of its bottom
corners — never by a model. Every page SHALL be saved as a `PaperPage` holding a JPEG with the long
side at most 2200 px under a random `paper_pages/<uuid>` key on the private media tier, with its
code (`printed_form`, `copy`, `page_number`, `pages_total`, `code_source='qr'`) when one decoded
and names a printed form of this survey. When all pages are saved the original upload SHALL be
deleted from storage, the upload marked `split` with its `pages_count`, and each page enqueued for
recognition. No image SHALL be decoded and no PDF parsed in a web request.

#### Scenario: Multi-page PDF
- **WHEN** a 12-page PDF scan is ingested
- **THEN** twelve `PaperPage` rows with consecutive `seq` exist, each with a JPEG, and the upload's file is gone from storage

#### Scenario: HEIC photo
- **WHEN** an iPhone HEIC photo is ingested
- **THEN** one page exists whose image is a JPEG the browser can display

#### Scenario: Not a document
- **WHEN** a `.docx` is ingested
- **THEN** the upload is `failed` with "Not a photo or PDF", no page exists and the file is deleted

#### Scenario: Code read at full resolution
- **WHEN** a 200-dpi render of page 2 of copy 141 is ingested
- **THEN** the page's `copy` is 141, `page_number` 2, `code_source` `qr`

### Requirement: The code decides where a page goes, never the order files arrived in
Placement SHALL be deterministic, under a lock on the inbox:
- a page of a numbered copy SHALL go to that copy's response (one per copy per inbox), created on
  first sight; an empty response the page was dropped into takes the copy instead; a page dropped
  into a different response SHALL still go to its own copy, and that response SHALL say where it went;
- a page of a form printed without numbers SHALL go to the response it was dropped into; else, a
  page of a PDF SHALL go to the response of that upload (one PDF = one response, created on first
  sight); else it SHALL be set aside ("add this photo to a response, or upload one PDF per filled form");
- a page dropped into a response for a known page whose code will not read SHALL be taken for that
  page of that response (`code_source='manual'`); a page dropped into a response whose form code
  will not read but which shows this survey's page-1 online-link QR (`utm_source=paper`,
  `utm_medium=print_form`) SHALL be page 1 of that response's form (or of the survey's only printed
  form); any other page without a code SHALL be set aside, and when it was dropped into a response,
  that response SHALL offer "It is page [n]" + *Attach* beside the warning (the first missing page
  preselected);
- a page whose response is stored, or whose printed form differs from the response's, SHALL be set
  aside with the reason;
- a second page with the same number on one response SHALL win, the earlier becoming `replaced`
  and restorable; once the new photo is read, stored answers that still equal what the earlier
  reading put in (the operator pressed Next without touching them) SHALL be deleted so the new
  reading prefills, and anything the operator changed SHALL stay.
Every notice on a response page (a replaced photo, a photo set aside from it, a photo that went to
its own copy) SHALL carry ×: it deletes a replaced or set-aside photo, and only clears the note of a
photo that went to another response, which stays there.
A set-aside page SHALL be `unrecognised` with its reason, listed with *Add to response* (a response
and a page number; `code_source='manual'`) and *Remove*; nothing SHALL be read from it until added.
Placement SHALL happen at ingest, before any model call, so the operator sees every photo land in
its slot while the stack is still uploading; the model reads SHALL be queued only once the inbox's
uploads have settled (none queued, none newer than a few seconds), in response and page order — a
read never stands between an upload and its slot. A response's notes (replaced photos, photos
that went to their own copy, photos set aside from it) SHALL sit in ONE collapsible block with a
count and *Dismiss all*, which deletes the replaced and set-aside photos and clears the notes of
the photos that went elsewhere. File questions SHALL NOT be printed at all: nothing can be
answered on paper, and the stub took space.
A response SHALL be `recognising` while a page is queued, `review` when it holds pages 1…N of its
form, `incomplete` otherwise.

#### Scenario: Shuffled stack of numbered copies
- **WHEN** pages 2 of copy 7, 1 of copy 3, 1 of copy 7 and 2 of copy 3 are uploaded in that order
- **THEN** two responses exist, Copy 3 and Copy 7, each with pages 1 and 2, both `review`

#### Scenario: Wrong card
- **GIVEN** Copy 3's card
- **WHEN** a photo of copy 7 page 1 is dropped on it
- **THEN** the page is on Copy 7 and Copy 3's card says "This photo is Copy 7, page 1 — it went there"

#### Scenario: Loose photo of an unnumbered form
- **WHEN** a single photo of a form printed without numbers is uploaded through *Upload a stack*
- **THEN** it is set aside with the reason and no response is created

#### Scenario: One PDF per form
- **WHEN** two three-page PDFs of an unnumbered form are uploaded through *Upload a stack*
- **THEN** two responses exist, each with pages 1–3

#### Scenario: Footer cut off on page 1
- **GIVEN** a New response and a form printed without copy numbers
- **WHEN** a photo of page 1 whose footer is out of frame but whose online-link QR is in it is dropped in
- **THEN** it is page 1 of that response, read by the local decoder

#### Scenario: Say which page
- **GIVEN** a response missing page 1 and a photo dropped into it with no readable code
- **WHEN** the response page renders and the operator picks page 1 and presses *Attach*
- **THEN** the photo joins the response as page 1 and the response page opens again

#### Scenario: Re-shot page supersedes untouched answers
- **GIVEN** page 1 read as ALB = Yes and WHY = "dark", saved with Next, then WHY changed by the operator to "too dark"
- **WHEN** page 1 is photographed again and read as ALB = No, WHY = "darker"
- **THEN** ALB prefills No (its saved row is gone) and WHY stays "too dark"

#### Scenario: Duplicate page
- **WHEN** page 2 of copy 7 is photographed twice
- **THEN** the later photo is on the response, the earlier is `replaced`, and *Restore* swaps them

#### Scenario: Copy already stored
- **GIVEN** Copy 7 is stored
- **WHEN** another photo of copy 7 arrives
- **THEN** it is set aside with "Copy 7 is already stored — this photo was not used"

### Requirement: One vision call per page, bounded by the page's items
Extraction SHALL send the page image and the items printed on that page — from
`PrintedForm.layout["<page>"]["items"]`, else the whole structure of the form's version with the
instruction to return only what the page shows — to the provider through
`complete_structured(images=…)`, in the form's language, with per question its code, type, name,
options (code and label, with the write-in flag), bounds and maximum. Geo, Objects-on-the-map,
file, `html` and `image` items SHALL NOT be asked. The response SHALL be
`{"fields": [{"code", "value", "confidence", "unreadable"}]}` with typed values (choice → option
code, multichoice and ranking → codes, number/range/rating → the number as text, thumbs →
`"1"`/`"0"`, text and datetime → the transcription, write-in → `<code>__other`), checked against
the question (an unknown option code becomes empty and doubtful). Each field MAY carry `box`
(`[ymin, xmin, ymax, xmax]`, 0–1000 of the photo) where the question sits; a box that is not four
in-range numbers with a positive area SHALL be dropped. On the check the form leads: the question
the operator is on (the focused field, else the card a third down the form's scroll area) SHALL
scroll the photo to its box and outline it on the photo and on its card; without a box (or on a
rotated photo) the photo SHALL keep the form's scroll proportion. A field with `confidence` below
`PAPER_DOUBTFUL_CONFIDENCE` (0.75) or `unreadable` SHALL be doubtful. Before the call
`check_quota(organisation, 'paper_page')` SHALL run and a refusal SHALL fail the page without a
call. The call SHALL be recorded as an `AIGenerationEvent` of kind `paper_page` with its usage and
outcome AND emitted at once to PostHog as `$ai_generation` (`$ai_span_name` = the kind,
`$ai_trace_id` = `paper-response-<response id>`, input/output tokens with thinking folded into
output, latency, `$ai_is_error` on failure, `survey_id`, `response_id`, `page_number`; never
content). A transient provider failure SHALL be retried twice, every attempt costed; a final
failure SHALL mark the page `failed` with *Retry*. A page that became `replaced` while being read
SHALL keep no result. The response's `extraction` SHALL merge its read pages' fields by code, an
earlier page winning, and `doubtful_count` SHALL count the doubtful fields.

#### Scenario: Choice and text on page 1
- **GIVEN** page 1 carries question `ALB` (choice Yes/No) and `WHY` (text)
- **WHEN** the page is extracted
- **THEN** the provider was called once with one image and exactly those two items, and the extraction holds an option code for `ALB` and text for `WHY`

#### Scenario: Geo question is not asked
- **GIVEN** a page with a point question and a choice question
- **WHEN** the page is extracted
- **THEN** the items sent name only the choice question

#### Scenario: Old form without an item map
- **GIVEN** a `PrintedForm` whose layout has no `items`
- **WHEN** a page of it is extracted
- **THEN** the whole structure is sent with the instruction to return only what the page shows

#### Scenario: Provider down
- **WHEN** the provider answers 503 on every attempt
- **THEN** the page is `failed`, three `AIGenerationEvent(kind='paper_page')` rows carry `provider_error`, and no `Answer` row exists

#### Scenario: Event per call
- **WHEN** a page is extracted
- **THEN** one `AIGenerationEvent(kind='paper_page')` exists with outcome `success`, and one `$ai_generation` was captured with `$ai_trace_id` `paper-response-<id>`, the token counts and no content

#### Scenario: Quota refuses
- **WHEN** `check_quota` raises for the organisation
- **THEN** the page is `failed`, the provider is not called and no event is written

#### Scenario: No model reads a code
- **WHEN** a page without a readable code, dropped nowhere, is recognised
- **THEN** it is set aside and the provider is never called

### Requirement: Marks on the printed map become coordinates
On a page that carries a map frame (`PrintedForm.layout[page]["map"]`), the page's vision call SHALL
also list the map questions of the frame's section with their legend letters (`A`, `B`, …, the
same `mark_letters` the form prints) and the readable sub-questions of their tables, and the model
SHALL report every mark drawn on the map — label (`A1`), question, vertices in 0–1000 of the photo,
confidence and the answers written in the mark's table row — and the box of the map frame. The
photo SHALL be registered locally (no model) by ONE weighted least-squares homography over every
landmark found, plus a bend correction: the residual the plane leaves at each landmark is
interpolated by a thin-plate spline (exact at the fiducials, loose at the page squares) and added
back, so a page bent in a hand or on a lap is read as it lies — on a flat page the correction is
zero. The frame's own border SHALL be sampled all around (dark line or paper-to-map step along
the normal, seven samples a side, the corners from the fitted lines) and join the fit; and the
printed map itself SHALL be a landmark: the frame image kept at print time (`ref_key` in the
frame record, re-rendered for forms printed before it was kept, never for the grid stand-in) is
matched against the photo rectified through the current registration — normalised
cross-correlation at a grid of anchors — and every clear match joins the fit and the spline, in
rounds until the matches sit where the fit predicts, because a page bows INSIDE its frame in ways
no border can tell. The landmarks: the fiducial squares printed beside the map frame (5 mm, 5 mm outside its left
and right edges — at its top, bottom AND halfway down each side; `map_rec["fiducials"]`,
`fiducial_dx_mm`, `fiducial_mids`),
searched around the corners of the model's frame box, any number of them (a tight crop loses one),
weight 50 each when three or more are found (they pin the map; the squares only settle what they
leave open) and 4 each with fewer; and the four page-corner squares (searched at full resolution, solid through — a QR
finder pattern has a white ring inside — accepted only when they form a portrait quadrilateral like
the page), weight 1 each. Paper on a table is never flat: the page corners alone put the middle of
the page 10 mm off, the fiducials beside the frame pin the map down. With fewer than four landmarks
the model's four corners of the frame (a trapezoid) register the photo, else its box; with none, the
marks are kept raw, the field is unreadable and the operator draws by hand. Dark-blob detection SHALL try thresholds from strict to loose, so a square touching a shadow
or the table edge still stands alone. The model SHALL report a mark's vertices as the ink of the
symbol itself, never centred on the label written next to it — and for a point question the
reader SHALL NOT take its word: with the printed map as the reference, the ink is what the rectified
photo has that the map does not, and the vertex moves to the nearest compact filled blob of it
(0.8–4.5 mm, within 7 mm; letters are strokes and do not qualify); without such a blob the
model's vertex stands. A vertex SHALL become a point of the frame (inside it or within 3 % of its edge, else
dropped) and then, through the frame's Web-Mercator bounds, a lng/lat. The marks' GEOMETRY SHALL come from the ink wherever the photo is registered to a kept or
re-rendered frame image: the ink is what is coloured against the paper around it (a blue pen) or
darker than the paper around it and than the darkest print beneath it (a black pen), never on
near-black print, and each connected piece of it is read as a hatched cluster
(a spray cloud of its own pixels), a closed loop (an area), a stroke with two ends (a line —
pieces whose ends lie within 8 mm are sewn, an outline whose ends meet is an area), a filled disc
(a point) or, glyph-sized and none of those, writing. The model's marks SHALL only name the ink:
each is paired with the ink mark of its question's kind its vertices lie along (median distance
within 25 mm; 8 mm for a glyph-sized piece), the geometry is the ink's and the label and row
answers the model's; a line's further pieces along one model mark are sewn onto it; ink the model
did not name becomes the next-numbered mark of the kind's only question on the page at confidence
0.5; a model mark the ink does not show keeps the model's vertices at confidence 0.6; ink under a
label the model boxed (`label_box`) is writing. A page that carries rows of a marks table whose map is on an earlier page (from the frame's page to
the page the question's own block lands on) SHALL be asked for those rows as marks without
geometry; their answers SHALL join the map page's marks by label and a label with no mark SHALL be
shown as an unplaced row with its answers. Marks SHALL become GeoJSON
features per geo question — a dot a Point, a drawn line a LineString of ≥ 2 vertices, an outlined
area a closed Polygon of ≥ 3, a shaded area a MultiPoint cloud sampled inside the outline — with the
table answers as properties in the shape stored answers already take, stored in the page's
extraction under the question's code, with where each mark is on the photo beside them. On the
check, the map questions of a frame's section SHALL be answered on the page that carries the frame
and on no other page. That page SHALL read like the paper, half and half with the photo: the printed
frame as a live map (same bounds, a button returns to them) with the marks pinned and labelled, then
per map question a table with the printed rows (A1…An, more when more marks were read) and the
printed columns — label, *placed* / *no mark*, the sub-questions as inputs (a select for one choice,
checkboxes for several), Show (the photo scrolls to the mark), remove — and *Add a mark the reader
missed*; an empty row offers *place it on the map* (a click for a dot, drawing for a line or area).
Selecting a row lights its pin and scrolls the photo to the mark; dragging a pin keeps the row's
answers. The page SHALL post the features in the section POST's own dialect through a hidden input
per map question, so saving stores them as any geo answer, and the next render SHALL show the STORED
rows. No respondent draw button and no pop-up SHALL render there. On paper, a choice column of the
marks table SHALL carry its boxes in every row (a numbered legend and "No. ___" beyond six options);
rating as boxes 1…5, thumbs as up/down. `paper_sheet_entered.fields_changed` SHALL count a geo
question as changed when the stored feature count differs from the placed one.

#### Scenario: A dot on a phone shot at an angle
- **GIVEN** a map page photographed at an angle, with a dot and "A1" drawn a third across and down the frame
- **WHEN** the page is read
- **THEN** the alignment squares register the photo, `WHERE` holds one Point feature a third across and down the frame's bounds, placed by `squares`, with the row's answer as a property

#### Scenario: Bent page
- **GIVEN** the map page photographed at an angle and bent along its long axis, with the table around it
- **WHEN** it is registered with the six fiducials and the page squares
- **THEN** the plane alone misses the middle of the frame by millimetres and the bend correction brings every point of the frame within 1 mm

#### Scenario: Bow inside the frame
- **GIVEN** the map page with a textured map, photographed at an angle, the middle of the map slid 4 mm sideways while its border and the fiducials stayed put
- **WHEN** it is registered without and with the printed map as the reference
- **THEN** the border alone misses the middle of the frame by more than 2 mm; with the reference the interior landmarks join the fit and every probe lands within 1 mm

#### Scenario: The marks table runs onto the next page
- **GIVEN** the map frame on one page and its marks table continuing on the next (the question's marker lands there), the frame page read with A1 placed and the next page reporting rows A1 ("shade") and A2 ("bench") without points
- **WHEN** both pages are read and the check opens the frame page
- **THEN** the next page was asked for the rows of that table and for no map, the response's field carries the rows beside the placed mark, A1's answer fills its row and A2 is an unplaced row with its answer for the operator to place

#### Scenario: The ink draws, the model names
- **GIVEN** a frame with a dot, line, area and spray question and, in blue ink: two dots, a 40-mm route in two pieces with a 6-mm skip, a 25-mm outline with a 3-mm gap, a hatched patch and "A2" written beside the first dot; the model reports A1 on those letters with their label_box, B1 along the route, C1 and D1 roughly, nothing for the second dot
- **WHEN** the marks are placed with the printed map as the reference
- **THEN** A1 is the first dot within 0.5 mm, the route one line spanning its 40 mm, the area a closed polygon 25 mm across, the patch a cloud of dots — all from the ink; the letters become nothing; the second dot is A2, numbered by the reader and flagged doubtful

#### Scenario: The dot, not the label
- **GIVEN** a registered map page with a 2-mm ink dot and "A1" written 4 mm to its right, and the model reporting the vertex on the letters
- **WHEN** the marks are placed with the printed map as the reference
- **THEN** the point lands on the dot within 0.5 mm, and a vertex with no dot-like ink near it is left where the model put it

#### Scenario: The printed map is kept
- **GIVEN** a form printed with a basemap
- **WHEN** the map page's record is read
- **THEN** it names the stored frame image, which the reader loads at the matcher's width; a form printed with the grid stand-in keeps none

#### Scenario: Cropped to the map, at an angle
- **GIVEN** a photo of the map page taken at an angle and cropped so no page corner is in it
- **WHEN** the fiducials beside the frame are searched around the model's frame box
- **THEN** all four are found, the photo registers through them and the frame's centre maps back within 1.5 mm

#### Scenario: No squares in frame
- **GIVEN** a photo at an angle of a form printed before the fiducials, cropped to the map
- **WHEN** the model reports the frame's four corners and a dot at its centre
- **THEN** the dot lands at the frame's centre through the corners, closer than the frame's box alone would put it; with neither, the field is unreadable and the raw marks are kept

#### Scenario: The map page reads like the paper and stores the rows
- **WHEN** the map page of the check renders
- **THEN** it is half and half, the marks table names A = the map question with its columns, the page's map data carries the features, their photo boxes and the printed row count, no draw button renders and the base map restores nothing
- **WHEN** the page is posted with the features the script serialises
- **THEN** a geo Answer with the row's sub-answers is stored and the next render shows the stored row

#### Scenario: Boxes in every printed row
- **GIVEN** a choice sub-question of a map question
- **WHEN** the form is printed
- **THEN** every row of the marks table carries the options as boxes

### Requirement: A response is checked page by page of the printed form, prefilled
`POST …/paper/r/<id>/check/` SHALL create the response's `SurveySession` when none exists —
`survey` = the printed form's version header, `language` = the form's language, `source='paper'`,
`entered_by` = the operator, `paper_sheet` = the response — and open page 1 of the printed form
(`…/r/<id>/pages/<n>/`); a form printed before the item map existed SHALL open the section flow of
the operator entry form instead. No `Answer` row SHALL exist until the operator saves a page. Page
`n` SHALL show the photograph of page `n` on the left (zoom, rotation; on a page with a map section
a toggle between the photograph and the map) and, on the right, exactly the questions printed on
page `n`, section by section in drawing order, prefilled from the extraction for every question
without an `Answer` row (stored rows win), with doubtful fields and fields the model saw blank
marked and "N fields to check" in the entry bar. A stepper SHALL list the pages with their state
and go to any page after saving the current one. Saving page `n` SHALL store only the questions
printed on it — a section that spans two pages keeps the other page's answers — and move to `n+1`,
or to the Saved page after the last; Back SHALL save and move to `n-1`. Page images SHALL be served
only through a gated view to members who may enter.

#### Scenario: Check starts from the form code
- **WHEN** the operator presses *Check* on Copy 7 of a Polish form of version 2
- **THEN** a session with `survey` = version 2's header, `language` `pl`, `source` `paper` and `paper_sheet` set exists, no `Answer` rows exist, and page 1 renders with its photograph and its questions only

#### Scenario: A section spanning two pages keeps both pages' answers
- **GIVEN** section S1 prints ALB and WHY on page 1 and MOOD on page 2
- **WHEN** page 1 is saved with ALB and WHY, then page 2 with MOOD
- **THEN** ALB, WHY and MOOD are all stored

#### Scenario: Saved rows win
- **GIVEN** the operator changed `WHY` and saved the page
- **WHEN** the page is opened again
- **THEN** the field shows the saved text, not the extraction

#### Scenario: Image is gated
- **WHEN** a viewer requests a page image URL
- **THEN** the response is 403

### Requirement: A page that was not photographed is attached from the check
When the response holds no image for page `n`, page `n` SHALL say so in place of the photograph,
with *Take photo* and *choose files*, and SHALL still let the operator fill the fields by hand or
press Next. A file attached there SHALL be uploaded with `sheet` and `page_number = n`, placed by the
rules above. The page SHALL poll `…/pages/<n>/status/` (`missing` | `queued` | `recognised` |
`failed` | `set_aside` with the reason) and reload with the fields filled once the page is read.

#### Scenario: Attach a missing page
- **GIVEN** Response 4 with page 1 only, of a two-page unnumbered form
- **WHEN** the operator opens page 2, attaches a photo whose QR will not decode, and the worker reads it
- **THEN** the page is on Response 4 as page 2 (`code_source` `manual`), the status answers `recognised`, and page 2 renders with the photograph and filled fields

#### Scenario: Status before and during
- **WHEN** page 2 is missing and nothing is uploading
- **THEN** the status answers `missing`; while an attached file is queued it answers `queued`

### Requirement: Saving the last page stores the response and offers the next one
Saving the last page of a response SHALL complete the session, mark the response `entered` with
`entered_at`, delete its page images (rows stay), emit `paper_sheet_entered` with `fields_total`,
`fields_doubtful` and `fields_changed` (prefill values the stored answers differ from), and render
the Saved page ("Copy 7 stored") whose *Check next* opens the next response to check, or *Paper
responses* when none remains. *Delete* on an open response SHALL delete it whole — pages, images,
its unfinished session to the trash, the row — so its copy number can be uploaded again; a stored
response is deleted on Responses, never here.

#### Scenario: Stored
- **WHEN** the operator saves the last page of Copy 7
- **THEN** the session has `end_datetime`, the response is `entered`, its pages have no image and one `paper_sheet_entered` event carries the three counts

#### Scenario: Deleted
- **WHEN** the operator deletes Copy 7 while it is being checked
- **THEN** its pages and images are gone, its session is trashed, the row is gone, and a new photo of copy 7 makes Copy 7 anew

### Requirement: Images live until the response is done; untouched responses are swept
Page images SHALL exist only while their response is open (`recognising`, `review`, `incomplete`)
or the page is set aside. The management command `sweep_paper_batches` SHALL report (default) or,
with `--delete`, delete every open response whose `last_activity_at` is older than
`PAPER_BATCH_TTL_DAYS` (default 30) whole, and delete the images of set-aside pages and the
originals of uploads older than that; stored responses SHALL stay. It SHALL run from
`reclaim.sh`. `/trust/` SHALL state this retention and that the model provider receives the page
image for the duration of the call.

#### Scenario: Sweep
- **GIVEN** a response last touched 31 days ago in `review`
- **WHEN** `sweep_paper_batches --delete` runs
- **THEN** the response, its pages and images are gone

#### Scenario: Dry run
- **WHEN** `sweep_paper_batches` runs without `--delete`
- **THEN** it lists what it would delete and deletes nothing

### Requirement: Paper responses are creator events, never content
The system SHALL emit server-side `paper_response_created` (`survey_id`, `surface`),
`paper_page_recognised` (`survey_id`, `outcome`: recognised | unrecognised | failed, `code_source`,
`doubtful`) and `paper_sheet_entered` (`survey_id`, `fields_total`, `fields_doubtful`,
`fields_changed`) with those properties and nothing else — no page content, no file names.

#### Scenario: Recognised event
- **WHEN** a page is recognised with two doubtful fields through the QR
- **THEN** one `paper_page_recognised` event has `outcome` `recognised`, `code_source` `qr`, `doubtful` 2 and no other property

### Requirement: Responses, the drawer and exports name the paper copy
The Responses detail drawer SHALL show, for a session with `paper_sheet`, the response's label
("Copy 7" / "Response 4") linking to its page; the `sessions` export table SHALL carry `paper_copy`
(the copy number printed on the paper, blank otherwise), so the original can be found in the folder.

#### Scenario: Drawer
- **WHEN** the drawer opens on a session entered from copy 7
- **THEN** it shows "Copy 7" linking to that response

#### Scenario: Export column
- **WHEN** the workbook export runs
- **THEN** the `sessions` sheet has a `paper_copy` column holding 7 for that session and blank for online sessions

