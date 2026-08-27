## ADDED Requirements

### Requirement: Three file question types collect respondent files

The platform SHALL offer `photo`, `audio` and `document` question types that collect a file from
the respondent, usable both as section questions and as sub-questions of geo questions.

#### Scenario: A photo question on mobile offers the camera

- **WHEN** a respondent opens a photo question on a mobile browser
- **THEN** activating the input offers the device camera directly
- **AND** picking an existing image remains possible

#### Scenario: A file sub-question rides the geo popup

- **WHEN** a respondent maps a feature whose geo question has a photo sub-question
- **THEN** the popup offers the photo input
- **AND** the submitted feature's attributes include the uploaded file

#### Scenario: Video is not offered

- **WHEN** a creator opens the question type picker
- **THEN** no video question type exists

### Requirement: Voice recording is offered where the browser supports it

An `audio` question SHALL offer in-browser voice recording when the browser provides MediaRecorder
and the respondent grants microphone access, with the file input always available as the fallback.

#### Scenario: Recording produces an uploadable answer

- **WHEN** a respondent records audio, stops, and submits the section
- **THEN** the recording is stored as their answer to the audio question

#### Scenario: Denied microphone degrades to the file input

- **WHEN** microphone permission is denied or MediaRecorder is unavailable
- **THEN** the audio question still accepts an audio file
- **AND** no error is shown for the missing recorder

#### Scenario: A recording can be replayed and redone before submit

- **WHEN** a respondent finishes a recording
- **THEN** they can replay it and re-record, and only the final take is attached

### Requirement: Files upload asynchronously and answers carry references

File bytes SHALL be uploaded to a respondent-facing endpoint at selection time and stored
immediately; forms and geo-feature properties SHALL carry only an opaque reference to the stored
upload, which the section submit resolves and attaches.

#### Scenario: Upload happens before section submit

- **WHEN** a respondent picks a file
- **THEN** it uploads with visible progress while they continue the section
- **AND** the section POST carries no file bytes

#### Scenario: A reference is only attachable by its own session

- **WHEN** a section submit presents a reference created by a different survey session
- **THEN** the answer is not attached
- **AND** the rest of the section saves normally

#### Scenario: Resubmission keeps the file without re-uploading

- **WHEN** a respondent resubmits a section whose file answer they did not change
- **THEN** the stored file remains attached
- **AND** no second upload occurs

### Requirement: Uploads are validated server-side

The upload endpoint SHALL enforce, server-side: a per-type content allow-list (images exclude SVG),
magic-byte verification for image and PDF families, a platform size cap of 25 MB (creators may
lower per question, never raise), and per-session caps on file count and total bytes.

#### Scenario: A disallowed type is rejected

- **WHEN** an SVG or executable is uploaded to a photo question
- **THEN** the endpoint rejects it with a respondent-readable error
- **AND** nothing is stored

#### Scenario: A mislabelled file is caught

- **WHEN** a file claims an allowed content type but its magic bytes disagree (image/PDF families)
- **THEN** the endpoint rejects it

#### Scenario: Session caps bound abuse

- **WHEN** a session exceeds the per-session file count or total byte cap
- **THEN** further uploads are rejected until the section is submitted or files are replaced

### Requirement: Respondent files are private and never published

Respondent-uploaded files SHALL be stored in the private storage tier, served only through
expiring signed URLs to authorized creators, and SHALL never appear on public results pages or in
any publicly readable location.

#### Scenario: A stored file is not fetchable by URL alone

- **WHEN** an unauthenticated client requests a respondent file at its object URL
- **THEN** the request is denied

#### Scenario: Public results never expose files

- **WHEN** a public results page is rendered for a survey with file questions
- **THEN** no file content, filename or link derived from respondent uploads appears

### Requirement: Creators receive files in views and export

File answers SHALL be visible to authorized creators in the Responses table (filename link, photo
thumbnail) via expiring signed URLs, and included in the responses download ZIP with rows
referencing each file's path inside the archive.

#### Scenario: Responses table links the file

- **WHEN** a creator opens Responses for a survey with file answers
- **THEN** each file answer shows its original filename linking to the file
- **AND** the link stops working after it expires

#### Scenario: The responses ZIP contains the files

- **WHEN** a creator downloads survey data
- **THEN** each attached file is present in the archive
- **AND** the corresponding CSV/GeoJSON value names that file's path within the archive

### Requirement: Orphaned uploads are reclaimed

Uploads never attached to a submitted answer SHALL be deleted, files included, after a grace
period long enough to span an interrupted respondent session.

#### Scenario: An abandoned upload is removed

- **WHEN** an upload remains unattached past the grace period and reclamation runs
- **THEN** its stored file and record are deleted

#### Scenario: A fresh unattached upload survives

- **WHEN** reclamation runs during a respondent's active session
- **THEN** uploads inside the grace period are retained

### Requirement: The feature has a kill switch

A `FILE_UPLOAD_QUESTIONS` environment variable, default on, SHALL gate the feature. Off: the
picker group is absent, the upload endpoint does not serve, and existing file questions render
nothing for respondents while the rest of the section continues to work.

#### Scenario: Switch off fails open for respondents

- **WHEN** the switch is off and a respondent opens a section containing a file question
- **THEN** the section renders and submits without the file question
