## ADDED Requirements

### Requirement: Changelog entries are files in the repository

The system SHALL read changelog entries from `survey/changelog/*.html`. Each file MUST start
with a header block delimited by `---` lines holding `key: value` pairs (`title` required,
`kind` ∈ `new`/`fixed` required, `link` optional URL name, `image` optional static path) followed
by an HTML body. The entry id SHALL be the filename stem and MUST match
`^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`. Entries SHALL be ordered by id descending and loaded once per
process. Entries are English only; the system SHALL NOT translate them.

#### Scenario: A well-formed entry is loaded
- **WHEN** `survey/changelog/2026-10-06-empty-sessions.html` exists with a valid header
- **THEN** `changelog.entries()` contains an entry with id `2026-10-06-empty-sessions`, the
  title, kind, link, image and the HTML body from the file

#### Scenario: Newest entry first
- **WHEN** two entries `2026-09-29-export-formats` and `2026-10-06-empty-sessions` exist
- **THEN** `changelog.entries()[0].id` is `2026-10-06-empty-sessions` and `changelog.latest()`
  returns it

#### Scenario: A malformed entry is rejected
- **WHEN** an entry file lacks a `title`, has an unknown `kind`, or a filename not matching the
  id pattern
- **THEN** loading raises an error naming the file, and the test suite fails on that file

#### Scenario: No entries
- **WHEN** `survey/changelog/` holds no entry files
- **THEN** `changelog.entries()` is empty and `changelog.latest()` is `None`

### Requirement: Seen-state is a per-user watermark

`CreatorPreferences` SHALL hold `changelog_seen` (the id of the newest entry the user has
seen, empty by default) and `changelog_cards` (default true). An entry is unseen for a user
when its id is greater than `changelog_seen`. Marking seen SHALL set `changelog_seen` to the
latest entry id. A user with no `CreatorPreferences` row SHALL be treated as `changelog_seen=''`
and `changelog_cards=True`.

#### Scenario: Existing creator sees the first entry
- **WHEN** a creator registered before any entry existed opens an editor page after the first
  entry ships
- **THEN** that entry is unseen for them

#### Scenario: Marking seen covers skipped entries
- **WHEN** three entries are newer than the user's watermark and the user is marked seen
- **THEN** `changelog_seen` equals the newest id and no entry is unseen

### Requirement: New accounts start with everything seen

On `user_registered` the system SHALL create the user's `CreatorPreferences` with
`changelog_seen` equal to the latest entry id (empty when there are no entries).

#### Scenario: Fresh registration
- **WHEN** a user registers while entries exist
- **THEN** no card is shown on their first editor page and the page shows no "New" highlight

### Requirement: The card shows the latest unseen entry once

The system SHALL show a card on every page extending `editor_base.html` or `base.html`
(dashboard, organization pages) to a signed-in user with at least one unseen entry and
`changelog_cards` on, with the latest entry (title, body, picture when set,
date, "Got it", "All updates", "Don't show these"). The card SHALL NOT render on respondent
pages (any path under `/surveys/` or `/r/`, whichever base template the page extends), for
anonymous users, when every entry is seen, or when `changelog_cards` is off.

#### Scenario: Card appears for an unseen entry
- **WHEN** a signed-in creator with `changelog_seen=''` opens the dashboard and an entry exists
- **THEN** the response contains the card with that entry's title

#### Scenario: Card does not appear once seen
- **WHEN** the same creator has `changelog_seen` equal to the latest id
- **THEN** the response contains no card

#### Scenario: Card respects the preference
- **WHEN** `changelog_cards` is false and an entry is unseen
- **THEN** the response contains no card, and the navbar still shows the unseen indicator

#### Scenario: Respondent pages never carry the card
- **WHEN** a signed-in creator opens their own survey as a respondent (`/surveys/<id>/…`)
- **THEN** the response contains no card markup

### Requirement: Dismissing the card marks everything seen

`POST /editor/whats-new/seen/` with `how` ∈ `got_it`/`close` SHALL set the watermark to the
latest id, emit `changelog_card_dismissed` with `entry_id` and `how`, and return 204. It SHALL
require a signed-in user.

#### Scenario: Got it
- **WHEN** a signed-in creator posts `how=got_it`
- **THEN** `changelog_seen` is the latest id and the next editor page has no card

#### Scenario: Anonymous
- **WHEN** an anonymous client posts to the endpoint
- **THEN** the response is a redirect to login and nothing is written

### Requirement: The What's new page lists every entry and marks them seen

`GET /editor/whats-new/` SHALL render every entry newest first, highlight the entries unseen
at the time of the request, show the card preference switch, then set the watermark to the
latest id and emit `changelog_page_viewed`. With no entries the page SHALL say so. The page
SHALL require a signed-in user and SHALL be reachable regardless of `changelog_cards`.

#### Scenario: Unseen entries highlighted on this render only
- **WHEN** a creator with one unseen entry opens the page
- **THEN** that entry is highlighted on this response, and `changelog_seen` equals the latest id
  afterwards, so a reload shows no highlight

#### Scenario: Entry link
- **WHEN** an entry has `link` set
- **THEN** the page shows an "Open" link resolving that URL name; without `link` no such link
  is shown

### Requirement: The card preference is per user

`POST /editor/whats-new/cards/` with `enabled` ∈ `0`/`1` SHALL set `changelog_cards`. When
`enabled=0`, the system SHALL also set the watermark to the latest id and emit
`changelog_card_dismissed` with `how=muted`.

#### Scenario: Mute from the card
- **WHEN** a creator posts `enabled=0`
- **THEN** `changelog_cards` is false, `changelog_seen` is the latest id, and the next editor
  page shows no card

#### Scenario: Re-enable
- **WHEN** the creator posts `enabled=1`
- **THEN** `changelog_cards` is true; already-seen entries do not produce a card

### Requirement: Entry points in the editor chrome

`editor_base.html` and `base.html` SHALL show a "What's new" item in the account menu (and in
the editor's mobile overflow menu) with a badge carrying the unseen count when it is non-zero, and a gift icon in
the desktop navbar with a dot when the count is non-zero. Both SHALL link to the page.

#### Scenario: Unseen indicator
- **WHEN** a creator has two unseen entries
- **THEN** the menu item badge reads "2" and the navbar icon carries the dot

#### Scenario: All seen
- **WHEN** a creator has no unseen entries
- **THEN** the menu item has no badge and the icon no dot

### Requirement: Changelog events reach PostHog

The system SHALL emit `changelog_card_shown` (browser, guarded by `window.posthog`),
`changelog_card_dismissed` (server, `how`) and `changelog_page_viewed` (server), each with `entry_id`. Server-side
emission SHALL be a no-op when PostHog is unconfigured.

#### Scenario: Dismiss emits
- **WHEN** PostHog is configured and a creator posts `how=close`
- **THEN** `product_events.emit` is called with `changelog_card_dismissed`,
  `{'entry_id': <latest>, 'how': 'close'}`
