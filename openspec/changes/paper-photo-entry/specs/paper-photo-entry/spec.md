# paper-photo-entry

Photos or scans of filled paper forms become prefilled operator entries (change paper-photo-entry,
#495; epic #350 item 3): a batch of uploads, pages read by a vision model, sheets reviewed through
the entry form with the picture beside it.

## ADDED Requirements

### Requirement: A batch is opened from Responses under the operator entry gate
The Responses page SHALL offer *From photos* beside *Type in a response* under *Enter a response*,
to members with the `editor` role or above, gated per request by the Pro feature `operator_entry`
on the organisation that owns the survey (the same gate as the entry header). The batch pages
SHALL be served at `/editor/surveys/<uuid>/responses/paper/` (this survey's batches, *New batch*)
and `/editor/surveys/<uuid>/responses/paper/<batch>/`; a batch of another survey SHALL answer 404.
A batch SHALL stay `open` until closed by the operator or the sweep, and files MAY be added to an
open batch at any time.

#### Scenario: Editor of a Pro workspace opens a batch
- **WHEN** an `editor` of a Pro organisation clicks *From photos* and *New batch*
- **THEN** a `PaperBatch` for the canonical survey exists and its page renders with the drop zone

#### Scenario: Viewer cannot
- **WHEN** a `viewer` requests the batch list URL
- **THEN** the response is 403

#### Scenario: Free workspace sees the refusal
- **WHEN** an `editor` of a Free organisation requests the batch list URL
- **THEN** the response is the `require_feature` refusal

#### Scenario: Another survey's batch
- **WHEN** an editor requests `/responses/paper/<batch>/` with a batch of a different survey
- **THEN** the response is 404

### Requirement: Files upload one per request to the private media tier
`POST /editor/surveys/<uuid>/responses/paper/<batch>/upload/` SHALL take exactly one file
(multipart `file`), create a `PaperUpload` with the next `seq` of the batch, store the file on the
private media tier under a random `paper_uploads/<uuid>` key without reading its content in the
request, enqueue the ingest task and answer JSON `{id, seq}`. A file over `PAPER_UPLOAD_MAX_BYTES`
(default 40 MB) SHALL answer 413 with a message; a batch at `PAPER_BATCH_MAX_PAGES` (default 500)
or `closed` SHALL answer 409. The batch page SHALL upload the selected files with at most three in
flight, show progress per file, retry a failed request once, and keep the drop zone active while
earlier files are being recognised.

#### Scenario: Thirty photos at once
- **WHEN** the operator drops thirty JPEGs on an open batch
- **THEN** thirty `PaperUpload` rows exist with `seq` 1…30 in the order the server received them and thirty ingest tasks are enqueued

#### Scenario: File too large
- **WHEN** a 60 MB file is posted
- **THEN** the response is 413, no `PaperUpload` is created and the page shows the message on that file's row

#### Scenario: Closed batch
- **WHEN** a file is posted to a `closed` batch
- **THEN** the response is 409 and nothing is stored

#### Scenario: Adding while recognising
- **GIVEN** a batch with pages still `queued`
- **WHEN** the operator drops three more files
- **THEN** they upload and are appended after the existing pages in `seq` order

### Requirement: Ingest splits, converts and normalises in the worker
The ingest task SHALL sniff the upload's type from its bytes and accept JPEG, PNG, WEBP, HEIC/HEIF
and PDF; anything else SHALL mark the upload `failed` with "Not a photo or PDF". A PDF SHALL be
rendered page by page at 150 dpi; an image SHALL be EXIF-transposed. Every page SHALL be saved as
a `PaperPage` holding a JPEG with the long side at most 2200 px under a random `paper_pages/<uuid>`
key on the private media tier, with consecutive `seq`s continuing the batch's order. When all pages
are saved the original upload SHALL be deleted from storage, the upload marked `split` with its
`pages_count`, and each page enqueued for recognition. No image SHALL be decoded and no PDF parsed
in a web request.

#### Scenario: Multi-page PDF
- **WHEN** a 12-page PDF scan is ingested
- **THEN** twelve `PaperPage` rows with consecutive `seq` exist, each with a JPEG, and the upload's file is gone from storage

#### Scenario: HEIC photo
- **WHEN** an iPhone HEIC photo is ingested
- **THEN** one page exists whose image is a JPEG the browser can display

#### Scenario: Not a document
- **WHEN** a `.docx` is ingested
- **THEN** the upload is `failed` with "Not a photo or PDF", no page exists and the file is deleted

#### Scenario: Big photo is bounded
- **WHEN** a 6000 × 4000 px photo is ingested
- **THEN** the stored page is at most 2200 px on its long side

### Requirement: The form code is read from the page, locally first
Recognition SHALL read the page's form code: first by decoding the QR (`ms:form:<form>:<page>:<pages>`)
locally over the normalised page and over an upscale of its corners; when no QR decodes, through
one vision call that reads the footer text `MS-<form>-<page>`, parsed with the same tolerance as
`form_code.parse`. The page SHALL record `printed_form`, `page_number`, `pages_total` and
`code_source` (`qr` | `text`). A page with no readable code, or whose code names a `PrintedForm` of
a survey other than the batch's, SHALL be `unrecognised`: listed under *Not recognised* with
*Assign to form…* (the operator picks a printed form of this survey and the page number) and
*Remove*; nothing SHALL be extracted from it until assigned.

#### Scenario: QR on a phone photo
- **WHEN** a photo of a printed page 2 of form `7K` is recognised
- **THEN** the page's `printed_form` is form 7K, `page_number` 2 and `code_source` `qr`

#### Scenario: Footer text fallback
- **GIVEN** a scan whose QR is smudged
- **WHEN** the page is recognised
- **THEN** the code comes from the footer text, `code_source` is `text`, and extraction proceeds

#### Scenario: Someone else's form
- **WHEN** a page carries the code of another survey's printed form
- **THEN** the page is `unrecognised`, nothing is extracted, and the list offers *Assign* and *Remove*

#### Scenario: Assigned by hand
- **WHEN** the operator assigns an unrecognised page to form 7K page 1
- **THEN** the page is recognised as if its code had read so and extraction runs

### Requirement: Pages are grouped into sheets by order and page number
Placement SHALL process the batch's unplaced pages in `seq` order and stop at the first page still
`queued`. A page with `page_number` 1, or with no sheet to continue, SHALL start a new `PaperSheet`
with the next sheet `seq`; a page SHALL continue the batch's last sheet only when that sheet has
the same `printed_form` and the page number is its last page number + 1. A sheet SHALL be `review`
when it holds pages 1…`pages_total` of one form and `incomplete` otherwise; an incomplete sheet
SHALL still open for review and say which pages are missing. The operator SHALL be able to move a
page to another sheet or to a new sheet from the batch list; a moved page is `pinned` and SHALL
never be regrouped automatically. Removing a page SHALL delete its image and row and re-evaluate
its sheet.

#### Scenario: Sheets of three pages in order
- **WHEN** pages 1, 2, 3, 1, 2, 3 of the same form are recognised in `seq` order
- **THEN** two sheets exist, each `review`, each with pages 1…3

#### Scenario: A page is missing
- **WHEN** pages 1, 2, 1, 2, 3 are recognised
- **THEN** the first sheet is `incomplete` (page 3 missing) and the second is `review`

#### Scenario: Out-of-order worker completion
- **GIVEN** page `seq` 2 is recognised before page `seq` 1
- **WHEN** placement runs
- **THEN** nothing is placed until page 1 is recognised, and then both are placed in `seq` order

#### Scenario: Moved page stays
- **WHEN** the operator moves a page to a new sheet and more pages are recognised later
- **THEN** the moved page remains on that sheet

### Requirement: One vision call per page, bounded by the page's items
Extraction SHALL send the page image and the items printed on that page — from
`PrintedForm.layout["<page>"]["items"]`, else the whole structure of the form's version with the
instruction to return only what the page shows — to the provider through
`complete_structured(images=…)`, in the form's language, with per question its code, type, name,
options (code and label, with the write-in flag), bounds and maximum. Geo, Objects-on-the-map,
file, `html` and `image` items SHALL NOT be asked. The response SHALL be
`{"fields": [{"code", "value", "confidence", "unreadable"}]}` with typed values (choice → option
code, multichoice and ranking → codes, number/range/rating → the number as text, thumbs →
`"1"`/`"0"`, text and datetime → the transcription, write-in → `<code>__other`). A field with
`confidence` below 0.75 or `unreadable` SHALL be doubtful. Before the call `check_quota(organisation,
'paper_page')` SHALL run, and the call SHALL be recorded as an `AIGenerationEvent` of kind
`paper_page` with its usage and outcome AND emitted at once to PostHog as `$ai_generation`
(`$ai_span_name` = the kind, `$ai_trace_id` = `paper-batch-<batch id>`, input/output tokens with
thinking folded into output, latency, `$ai_is_error` on failure, `survey_id`, `batch_id`,
`page_number`; never content) — the footer-code fallback call likewise as kind `paper_code`.
A transient provider failure SHALL be retried twice; a
final failure SHALL mark the page `failed` with *Retry* in the list. The sheet's `extraction` SHALL
merge its pages' fields by code, an earlier page winning, and `doubtful_count` SHALL count the
doubtful fields.

#### Scenario: Choice and text on page 1
- **GIVEN** page 1 of form 7K carries question `ALB` (choice Yes/No) and `WHY` (text)
- **WHEN** the page is extracted
- **THEN** the provider was called once with one image and exactly those two items, and the page's extraction holds a value for `ALB` as an option code and for `WHY` as text

#### Scenario: Geo question is not asked
- **GIVEN** a page with a point question and a choice question
- **WHEN** the page is extracted
- **THEN** the items sent name only the choice question

#### Scenario: Doubtful field
- **WHEN** the model returns `WHY` with confidence 0.4
- **THEN** the sheet's `doubtful_count` includes it

#### Scenario: Old form without an item map
- **GIVEN** a `PrintedForm` whose layout has no `items`
- **WHEN** a page of it is extracted
- **THEN** the whole structure is sent with the instruction to return only what the page shows

#### Scenario: Provider down
- **WHEN** the provider answers 503 three times
- **THEN** the page is `failed`, the list shows *Retry*, and no `Answer` row exists

#### Scenario: Event per call
- **WHEN** a page is extracted
- **THEN** one `AIGenerationEvent(kind='paper_page')` exists with the organisation, the usage and outcome `ok`, and one `$ai_generation` was captured with `$ai_span_name` `paper_page`, `$ai_trace_id` `paper-batch-<id>`, the token counts and no content property

#### Scenario: Failed call is costed too
- **WHEN** the provider answers 503 and the retries are exhausted
- **THEN** the `$ai_generation` captured carries `$ai_is_error` true and whatever token usage the provider reported

### Requirement: The batch list shows every sheet, page and upload with its state
The batch page SHALL list uploads still `queued`/`failed` (with the error), sheets in `seq` order
with their state — recognising / review (N to check) / incomplete (pages missing) / entered /
skipped — and their pages as thumbnails, and unrecognised pages in their own group. It SHALL show
the batch's counts (sheets to review, entered, skipped, not recognised) and poll
`GET …/paper/<batch>/status/` every 3 seconds while any upload or page is in flight, re-rendering
the list. Each sheet SHALL offer *Review* (or *Continue* when a session exists) and *Skip*; the
batch SHALL offer *Close batch*.

#### Scenario: Live list
- **GIVEN** a batch with one sheet `review` and two pages `queued`
- **WHEN** the status endpoint is polled
- **THEN** it answers `in_flight: true` with the sheet's state and the page counts, and the list polls again

#### Scenario: Counts
- **GIVEN** a batch with 3 sheets to review, 5 entered, 1 skipped and 2 unrecognised pages
- **WHEN** the batch page renders
- **THEN** those four numbers are shown

### Requirement: A sheet is reviewed through the prefilled entry form
`POST …/paper/<batch>/sheets/<sheet>/enter/` SHALL create the sheet's `SurveySession` when none
exists — `survey` = the printed form's version header, `language` = the form's language,
`source='paper'`, `entered_by` = the operator, `paper_sheet` = the sheet — and redirect to the
first visible section of the operator entry flow; with a session it SHALL redirect to the first
section without a stored answer, else the first section. No `Answer` row SHALL exist until the
operator saves a section. Each entry section of a sheet session SHALL be prefilled from the sheet's
extraction for every question without an `Answer` row (a saved section's rows win), SHALL mark
doubtful fields and fields the model saw blank, SHALL show "N fields to check" in the entry bar,
and SHALL render the page pane: the image of the page whose items include the section (else the
sheet's first page), with zoom, rotation, a switcher over the sheet's pages and, on a `map`-layout
section, a toggle between the page and the map. Page images SHALL be served only through a gated
view to members who may enter.

#### Scenario: Review starts from the form code
- **WHEN** the operator presses *Review* on a sheet of form 7K (version 2, Polish)
- **THEN** a session with `survey` = version 2's header, `language` `pl`, `source` `paper` and `paper_sheet` set exists, no `Answer` rows exist, and the first entry section renders

#### Scenario: Prefilled fields
- **GIVEN** the sheet's extraction holds `ALB`=`yes` and `WHY`="Too dark at night"
- **WHEN** the section with those questions renders
- **THEN** the Yes radio is checked and the text area holds the transcription

#### Scenario: Saved rows win
- **GIVEN** the operator changed `WHY` and saved the section
- **WHEN** the section is opened again
- **THEN** the field shows the saved text, not the extraction

#### Scenario: Doubtful marked
- **GIVEN** `WHY` is doubtful
- **WHEN** the section renders
- **THEN** the section data lists `WHY` as doubtful and the entry bar says "1 field to check"

#### Scenario: Page pane follows the section
- **GIVEN** a two-page form whose page 2 items include `section:S2`
- **WHEN** section S2 renders
- **THEN** the pane shows page 2 with a switcher over pages 1 and 2

#### Scenario: Image is gated
- **WHEN** a viewer requests a page image URL
- **THEN** the response is 403

### Requirement: Saving the last section enters the sheet and offers the next one
Submitting the last visible section of a sheet session SHALL complete the session, mark the sheet
`entered` with `entered_at`, delete the sheet's page images (rows stay), emit `paper_sheet_entered`
with `fields_total`, `fields_doubtful` and `fields_changed` (prefill values the stored answers
differ from), and render the Saved page whose *Next sheet* opens the batch's next `review` or
`incomplete` sheet, or the batch list when none remains. *Skip* on a sheet SHALL mark it `skipped`,
delete its images and trash its empty session if one exists.

#### Scenario: Entered
- **WHEN** the operator saves the last section of a sheet
- **THEN** the session has `end_datetime`, the sheet is `entered`, its pages have no image and one `paper_sheet_entered` event carries the three counts

#### Scenario: Next sheet
- **GIVEN** the batch has another sheet in `review`
- **WHEN** the operator presses *Next sheet*
- **THEN** that sheet's review opens

#### Scenario: Skipped
- **WHEN** the operator skips a sheet that has an empty session
- **THEN** the sheet is `skipped`, its images are gone and the session is trashed

### Requirement: Images live until the sheet is done; untouched batches are swept
Page images SHALL exist only while their sheet is `recognising`, `review` or `incomplete`. The
management command `sweep_paper_batches` SHALL report (default) or, with `--delete`, close every
`open` batch whose `last_activity_at` is older than `PAPER_BATCH_TTL_DAYS` (default 30) and delete
its remaining page images and uploads; batch, sheet and page rows SHALL stay. The command SHALL
run daily from a Render cron. `/trust/` SHALL state this retention and that the model provider
receives the page image for the duration of the call.

#### Scenario: Sweep
- **GIVEN** a batch last touched 31 days ago with two sheets in `review`
- **WHEN** `sweep_paper_batches --delete` runs
- **THEN** the batch is `closed`, its page images are deleted and the rows remain

#### Scenario: Dry run
- **WHEN** `sweep_paper_batches` runs without `--delete`
- **THEN** it lists the batches it would close and deletes nothing

### Requirement: Batches are creator events, never content
The system SHALL emit server-side `paper_batch_created` (`survey_id`), `paper_page_recognised`
(`survey_id`, `outcome`: recognised | unrecognised | failed, `code_source`, `doubtful`) and
`paper_sheet_entered` (`survey_id`, `fields_total`, `fields_doubtful`, `fields_changed`) with those
properties and nothing else — no page content, no file names.

#### Scenario: Recognised event
- **WHEN** a page is recognised with two doubtful fields through the QR
- **THEN** one `paper_page_recognised` event has `outcome` `recognised`, `code_source` `qr`, `doubtful` 2 and no other property

### Requirement: Responses, the drawer and exports name the sheet
The Responses detail drawer SHALL state, for a session with `paper_sheet`, "Sheet N of batch M"
with a link to the batch; the `sessions` export table SHALL carry `paper_batch` and `paper_sheet`
(sequence numbers, blank for other sessions).

#### Scenario: Drawer
- **WHEN** the drawer opens on a session entered from sheet 7 of batch 3
- **THEN** it reads "Sheet 7 of batch 3" and links to the batch page

#### Scenario: Export columns
- **WHEN** the workbook export runs
- **THEN** the `sessions` sheet has `paper_batch` and `paper_sheet` columns, blank for online sessions
