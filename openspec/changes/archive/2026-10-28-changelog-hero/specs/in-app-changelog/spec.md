## MODIFIED Requirements

### Requirement: Changelog entries are files in the repository

The system SHALL read changelog entries from `survey/changelog/*.html`. Each file MUST start
with a header block delimited by `---` lines holding `key: value` pairs (`title` required,
`kind` ∈ `new`/`fixed` required, `link` optional URL name, `image` optional static path, and
the hero keys of capability `changelog-hero-banner`: `tier`, `art`, `eyebrow`, `link_query`,
`cta_label`, `help`, `chips`, `show_if`, `note_if`, `note`) followed by an HTML body. `tier`
defaults to `card`. The entry id SHALL be the filename stem and MUST match
`^\d{4}-\d{2}-\d{2}-[a-z0-9-]+$`. Entries SHALL be ordered by id descending and loaded once per
process. Entries are English only; the system SHALL NOT translate them.

#### Scenario: A well-formed entry is loaded
- **WHEN** `survey/changelog/2026-10-06-empty-sessions.html` exists with a valid header
- **THEN** `changelog.entries()` contains an entry with id `2026-10-06-empty-sessions`, the
  title, kind, link, image and the HTML body from the file, and `tier == 'card'`

#### Scenario: Newest entry first
- **WHEN** two entries `2026-09-29-export-formats` and `2026-10-06-empty-sessions` exist
- **THEN** `changelog.entries()[0].id` is `2026-10-06-empty-sessions` and `changelog.latest()`
  returns it

#### Scenario: A malformed entry is rejected
- **WHEN** an entry file lacks a `title`, has an unknown `kind`, an unknown header key, or a
  filename not matching the id pattern
- **THEN** loading raises an error naming the file, and the test suite fails on that file

#### Scenario: No entries
- **WHEN** `survey/changelog/` holds no entry files
- **THEN** `changelog.entries()` is empty and `changelog.latest()` is `None`

### Requirement: The card shows the latest unseen entry once

The system SHALL show a card on every page extending `editor_base.html` or `base.html`
(dashboard, organization pages) to a signed-in user with at least one unseen entry of
`tier: card` and `changelog_cards` on, with the latest such entry (title, body, picture when
set, date, "Got it", "All updates", "Don't show these"). The card SHALL NOT render while a
hero is pending for the user (capability `changelog-hero-banner`), and a hero entry SHALL
never render as a card. The card SHALL NOT render on respondent pages (any path under
`/surveys/` or `/r/`, whichever base template the page extends), for anonymous users, when
every entry is seen, or when `changelog_cards` is off. The card markup SHALL carry the entry
id and the page script SHALL hide a card whose id the browser remembers as closed.

#### Scenario: Card appears for an unseen entry
- **WHEN** a signed-in creator with `changelog_seen=''` opens the dashboard and a `card` entry
  exists and no hero is pending
- **THEN** the response contains the card with that entry's title

#### Scenario: Card does not appear once seen
- **WHEN** the same creator has `changelog_seen` equal to the latest id
- **THEN** the response contains no card

#### Scenario: Card yields to a pending hero
- **WHEN** a hero newer than the creator's watermark is pending and an older `card` entry is
  also unseen
- **THEN** no small card renders on any page; the dashboard renders the hero

#### Scenario: Hero entry is skipped by the card
- **WHEN** the only unseen entry is a hero that is no longer pending (expired or out of audience)
- **THEN** no small card renders

#### Scenario: Card respects the preference
- **WHEN** `changelog_cards` is false and an entry is unseen
- **THEN** the response contains no card, and the navbar still shows the unseen indicator

#### Scenario: Respondent pages never carry the card
- **WHEN** a signed-in creator opens their own survey as a respondent (`/surveys/<id>/…`)
- **THEN** the response contains no card markup

### Requirement: Dismissing the card marks everything seen

`POST /editor/whats-new/seen/` with `how` ∈ `got_it`/`close`/`cta` SHALL set the watermark to
the latest id, emit `changelog_card_dismissed` with `entry_id`, `how` and `tier` (the tier of
the entry the creator closed, `card` or `hero`, sent as `entry_id`), for `how=cta` also emit
`changelog_card_clicked` with `entry_id`, `tier` and `target=cta`, and return 204. It SHALL
require a signed-in user. The browser SHALL emit `changelog_card_shown` with `entry_id` and
`tier` when a card or hero renders, and `changelog_card_clicked` with `target=help` when the
hero's secondary link is followed.

#### Scenario: Got it
- **WHEN** a signed-in creator posts `how=got_it`
- **THEN** `changelog_seen` is the latest id and the next editor page has no card

#### Scenario: Call to action
- **WHEN** a signed-in creator posts `how=cta` with the hero's `entry_id`
- **THEN** `changelog_seen` is the latest id, and both `changelog_card_clicked` and
  `changelog_card_dismissed` carry `tier=hero`

#### Scenario: Anonymous
- **WHEN** an anonymous client posts to the endpoint
- **THEN** the response is a redirect to login and nothing is written
