## ADDED Requirements

### Requirement: A thread is anchored to exactly one survey object
The system SHALL store a comment thread against the canonical survey with exactly one anchor:
the survey itself (a general thread, no object fields), a question (by `question_code`), a
section (by `section_code`), a respondent session (by FK) or a public-results block (by FK).
The database SHALL reject a thread with more than one anchor, or an anchor that does not match
`anchor_kind`.

#### Scenario: General thread from the whole-survey view
- **WHEN** a member opens the drawer from the toolbar and posts in the composer at the bottom
- **THEN** a thread with `anchor_kind=survey` and no object fields is created and listed first under "Survey: general"

#### Scenario: Thread opened on a question from a draft copy
- **WHEN** a member opens a thread on a question while editing a draft copy of a published survey
- **THEN** the thread is stored with `survey` = the canonical survey and `question_code` = that question's code

#### Scenario: Two anchors rejected
- **WHEN** a thread row is saved with both `question_code` and `section_code` set
- **THEN** the database raises an integrity error and nothing is stored

### Requirement: Threads survive publishing
A thread anchored to a question or section SHALL remain visible on that question or section
after the survey is published again, because the anchor is resolved by code against the
canonical survey's current rows.

#### Scenario: Publish moves the rows, the thread stays
- **WHEN** a thread exists on question `Q_1` of a published survey, a draft is created, edited and published
- **THEN** the thread resolves to the new canonical row with code `Q_1` and shows on that question's row and in the drawer

#### Scenario: Anchored object deleted
- **WHEN** the question a thread is anchored to is deleted from the survey
- **THEN** the thread is listed in the drawer under "No longer in the survey", still counts in the toolbar total, and no page errors

### Requirement: Every survey role may take part
Any user with an effective survey role of viewer or above SHALL be able to open a thread,
reply, resolve and reopen a thread, and delete their own comment. A user with the owner role
SHALL be able to delete any comment. Users without a role SHALL receive 403/404 on every
comment endpoint.

#### Scenario: Viewer resolves a thread
- **WHEN** a viewer POSTs to the resolve endpoint of an open thread
- **THEN** the thread is marked resolved with `resolved_by` = the viewer and the drawer shows it under Resolved

#### Scenario: Editor deletes another member's comment
- **WHEN** an editor POSTs delete on a comment written by someone else
- **THEN** the response is 403 and the comment is unchanged

#### Scenario: Owner deletes another member's comment
- **WHEN** an owner POSTs delete on a comment written by someone else
- **THEN** the comment is soft-deleted, its body cleared, its attachments removed from storage, and the thread keeps its other comments

#### Scenario: Outsider denied
- **WHEN** a signed-in user from another organization requests the drawer of a survey
- **THEN** the response is 403 or 404 and no thread content is included

### Requirement: Comment body is plain text with mentions
The system SHALL store a comment body as plain text and render it escaped with line breaks
preserved. Mentions SHALL be stored as a many-to-many relation to users who are members of
the survey's organization and rendered as chips; a mention of a non-member SHALL be ignored.

#### Scenario: HTML in a comment is shown as text
- **WHEN** a member posts a comment whose body contains `<script>alert(1)</script>`
- **THEN** the drawer renders the literal text and no script element exists in the response

#### Scenario: Mention autocomplete lists workspace members
- **WHEN** a member requests the mention list for a survey
- **THEN** every member of the survey's organization is listed, including org owners without a `SurveyCollaborator` row, and nobody else

### Requirement: Attachments are private and gated
A comment MAY carry attachments (images and files). Files SHALL be stored on the private
media tier under a random key and SHALL be served only through a view that requires a survey
role. Uploads over 15 MB or of a disallowed type SHALL be rejected with a message.

#### Scenario: Attachment download by a member
- **WHEN** a viewer requests an attachment of a comment on their survey
- **THEN** the response is the file (locally) or a redirect to a signed URL (S3)

#### Scenario: Attachment download by an outsider
- **WHEN** a user without a role on the survey requests the attachment URL
- **THEN** the response is 403 or 404

#### Scenario: Oversized upload
- **WHEN** a member attaches a 20 MB file
- **THEN** the comment is not created and the response says the limit is 15 MB

### Requirement: Badges show open thread counts
Section rows, question rows and public-results block rows in the editor SHALL show a badge
with the number of open threads on that object. A section's count SHALL include threads on
the questions inside it. Counts SHALL be computed with one grouped query per page render,
and SHALL be refreshed on the page after any thread action without a reload.

#### Scenario: Badge on a question row
- **WHEN** a question has two open threads and one resolved thread
- **THEN** its row shows `2` and the section containing it includes those two in its own count

#### Scenario: Badge after an HTMX swap
- **WHEN** a question with an open thread is duplicated, edited or its section is re-rendered by any editor endpoint
- **THEN** the returned row partial still carries the badge with the right count

#### Scenario: Badge after resolving
- **WHEN** a member resolves the only open thread of a question from the drawer
- **THEN** the badge on that row disappears without a page reload

### Requirement: One drawer on every editor page
The survey page, the question modal and the public-results config SHALL open the same
comments drawer from the right; on viewports below the mobile breakpoint it SHALL take the
full width. The drawer SHALL list the survey's threads grouped by anchor with Open and
Resolved filters, Open by default, and a composer pinned at the bottom that targets the
focused anchor. Opening from a badge or a modal button SHALL focus that anchor's threads. On
Responses the thread of a session SHALL render inside the session detail surface under Tags &
Notes.

#### Scenario: Drawer from a badge
- **WHEN** a member clicks the badge on a section row
- **THEN** the drawer opens focused on that section's threads and the composer placeholder names the section

#### Scenario: Drawer above the question modal
- **WHEN** the question modal is open and the member clicks its "Comments" button
- **THEN** the drawer opens above the modal filtered to that question, and closing the drawer leaves the modal open

#### Scenario: Thread inside the session drawer
- **WHEN** a member opens response #N on Responses
- **THEN** the session detail shows the thread for that session below Tags & Notes with a composer

### Requirement: Deep links open the thread
The system SHALL accept `#thread-<id>` on the survey, responses and public-results pages,
open the drawer on that thread and scroll to it, after opening the section or block the
anchor belongs to.

#### Scenario: Email link to a question thread
- **WHEN** a member opens `editor_survey_detail?section=<id>#thread-<thread id>`
- **THEN** the section is selected, the drawer is open and the thread is expanded and scrolled into view
