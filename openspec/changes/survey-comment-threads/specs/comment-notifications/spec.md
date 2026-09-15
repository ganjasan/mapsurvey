## ADDED Requirements

### Requirement: Participants are notified by email
When a comment is posted, the system SHALL email every participant of the thread except the
actor. Participants are the thread's creator, the author of every comment in the thread and
every user mentioned in any comment of the thread. A new thread with no mention SHALL notify
nobody.

#### Scenario: Reply notifies the thread author
- **WHEN** member B replies in a thread opened by member A
- **THEN** exactly one email is sent, addressed to A, and none to B

#### Scenario: Mention adds a participant
- **WHEN** member A opens a thread mentioning member C
- **THEN** C receives an email and A does not

#### Scenario: Earlier mention keeps receiving
- **WHEN** C was mentioned three replies ago and D now replies without mentioning anyone
- **THEN** C receives an email for D's reply

### Requirement: Notification email content
The email SHALL name the actor, the object the thread is on (question, section, response or
block) and the survey, quote the comment body as text, list attachment names, and carry one
absolute link that opens the page with the drawer on that thread. Text and HTML parts SHALL
both be sent.

#### Scenario: Email for a question thread
- **WHEN** a notification is sent for a reply on question "White (albino) squirrel"
- **THEN** the subject contains the actor's name and the question name, and the body contains a link starting with `SITE_URL` and ending with `#thread-<id>`

### Requirement: Mail is sent by a Celery task per recipient
Notifications SHALL be enqueued after the database transaction commits, one task per
recipient, with retries on transport failure. A failure for one recipient SHALL not prevent
delivery to the others.

#### Scenario: Enqueued after commit
- **WHEN** a comment is posted and the transaction commits
- **THEN** one task per recipient is queued with the comment id and the recipient id

#### Scenario: Transport failure retries
- **WHEN** the SMTP connection fails while sending to one recipient
- **THEN** that task is retried up to three times and the other recipients' tasks are unaffected

### Requirement: Reusable templated mail helper and site URL
The system SHALL provide `send_templated_mail(template_prefix, to, subject, context)` that
renders `<prefix>.txt` and `<prefix>.html`, and `absolute_url(path)` that prefixes
`settings.SITE_URL`. `SITE_URL` SHALL default to the value of `NEWSLETTER_SITE_URL` so no
existing deployment changes behaviour.

#### Scenario: Absolute URL without a request
- **WHEN** a Celery task builds the thread link with `SITE_URL=https://mapsurvey.org`
- **THEN** the link is `https://mapsurvey.org/editor/surveys/<uuid>/?section=<id>#thread-<id>`
