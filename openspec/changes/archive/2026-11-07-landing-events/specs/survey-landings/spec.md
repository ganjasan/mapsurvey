## MODIFIED Requirements

### Requirement: Blocks are a closed set validated by one function
A landing SHALL hold an ordered list of blocks of the kinds `text`, `image`, `button`, `video`, `faq`, `timeline`, `survey`, `documents`, `map`, `results` and `event`, each with an optional title. Every write of a block SHALL pass `landings.clean_block(kind, data)`: rich text through `coerce_creator_html`, plain fields trimmed and capped, button URLs absolute `http(s)` only, video URLs accepted only when `layer_assets.embed_url` turns them into a YouTube or Vimeo player URL, FAQ 1–30 items, timeline 1–12 phases with an optional current phase, survey cards only for a survey linked to the same landing, map colours `#rrggbb` only, base maps only keys the workspace resolves, results only for a publishable question of a survey of the same workspace with a visualisation from its type's list, events only with a valid date, times, IANA time zone and a seat limit of 1–10000 or none. Unknown keys SHALL be dropped. Blocks SHALL be reordered by posting the full id list; ids of another landing SHALL be refused.

#### Scenario: Rich text is sanitised
- **WHEN** a text block is saved with `<p>Hello</p><script>alert(1)</script>`
- **THEN** the stored body is `<p>Hello</p>` without the script

#### Scenario: Unsafe button link refused
- **WHEN** a button block is saved with URL `javascript:alert(1)`
- **THEN** the save is refused with a field error naming the URL

#### Scenario: Video only from YouTube or Vimeo
- **WHEN** a video block is saved with `https://youtu.be/dQw4w9WgXcQ`
- **THEN** the stored embed is the YouTube player URL for that video, and a URL from another host is refused

#### Scenario: Reorder
- **WHEN** the builder posts the block ids in a new order
- **THEN** the blocks' order is 0..N in that order, and a list containing another landing's block id is refused with 400

## ADDED Requirements

### Requirement: Residents register for an event on the landing
An event block SHALL show the date, the time in the event's time zone, the place and the description, and, while registration is open and the event has not ended, a form with name, email and a consent line stating that the name and email are used only for this event and deleted 30 days after it. A registration SHALL be refused without consent or with an invalid email, SHALL be silently dropped when the honeypot is filled, and SHALL answer 429 after 5 registration posts per hour from one address. The seat limit SHALL hold under concurrent posts; a full event SHALL say so and store nothing. The same email SHALL hold at most one active registration per event; registering again SHALL send the confirmation again and store nothing new.

#### Scenario: Registration stored and confirmed
- **WHEN** a visitor registers "Ana" / "ana@example.org" with consent for an open event
- **THEN** one active registration exists, a confirmation mail with an `.ics` attachment and a cancel link goes to that address, and the page says to check the inbox

#### Scenario: Full event
- **WHEN** an event with 1 seat already has one active registration and a second visitor registers
- **THEN** no registration is stored and the page says the event is full

#### Scenario: Same email twice
- **WHEN** the same email registers twice for one event
- **THEN** one active registration exists and two confirmations were sent

#### Scenario: Honeypot and consent
- **WHEN** a post fills the hidden `website` field, or omits consent
- **THEN** nothing is stored

### Requirement: A registration can be cancelled from the confirmation mail
The cancel link SHALL open a page naming the event with a Cancel button; only a POST SHALL cancel, freeing the seat. An unknown token SHALL be 404.

#### Scenario: Cancel frees the seat
- **WHEN** the registrant of a 1-seat event posts the cancel form
- **THEN** the registration is cancelled and another visitor can register

### Requirement: The workspace sees and removes its attendees
Owners, admins and editors of the landing's workspace SHALL see each event's registrations (name, email, time, status), download them as CSV with formula-looking cells guarded, and remove one or all; viewers and outsiders SHALL not (403 / 404). Seeing and removing SHALL NOT need Pro. The builder SHALL show the count and seats left.

#### Scenario: Viewer refused
- **WHEN** a viewer opens an event's attendee list
- **THEN** the response is 403

#### Scenario: CSV
- **WHEN** an editor downloads the CSV of an event with a registrant named `=HYPERLINK("x")`
- **THEN** the file has a header and the name cell starts with an apostrophe

### Requirement: Registrations are deleted 30 days after the event
A daily task SHALL delete the registrations of events that ended more than 30 days before; deleting the event block or the landing SHALL delete its registrations. `/terms/` and `/trust/` SHALL state that landing-page event registration stores a name and an email for the organising workspace and deletes them 30 days after the event.

#### Scenario: Purge
- **WHEN** the task runs and one event ended 31 days ago and another ends tomorrow
- **THEN** the first event's registrations are gone and the second's remain

#### Scenario: Policy pages
- **WHEN** `/terms/` and `/trust/` render
- **THEN** both mention event registration and the 30-day deletion
