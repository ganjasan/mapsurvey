# in-app-changelog Specification

## Purpose

Tell creators, once and where they work, what changed in Mapsurvey and why: repository-authored
changelog entries, a once-only card in the editor, a What's new page with its entry points, a
per-user card preference, the seen-state watermark and the analytics events behind them.
## Requirements
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

The system SHALL show a *What's new* block in the application sidebar, above its footer, on every
page that carries the sidebar, to a signed-in user with `changelog_cards` on and an entry to
show: the pending hero (capability `changelog-hero-banner`) when there is one, else the latest
unseen entry of `tier: card`. The block SHALL carry the entry id and tier, its picture when set,
the date, the title, the hero's call to action when the entry is a pending hero with a resolvable
link, *Read more* linking to the What's new page, *Don't show these* and a ×. No other page
element SHALL render a changelog entry: there is no corner card and no dashboard banner. The
block SHALL NOT render on respondent pages, for anonymous users, when every entry is seen, when
`changelog_cards` is off, or in the sidebar's rail. The page script SHALL hide a block whose
entry id the browser remembers as closed.

#### Scenario: Block appears for an unseen entry
- **WHEN** a signed-in creator with `changelog_seen=''` opens the dashboard and a `card` entry
  exists and no hero is pending
- **THEN** the sidebar contains the block with that entry's id and title

#### Scenario: Block does not appear once seen
- **WHEN** the same creator has `changelog_seen` equal to the latest id
- **THEN** the response contains no block

#### Scenario: A pending hero takes the block
- **WHEN** a hero newer than the creator's watermark is pending and an older `card` entry is
  also unseen
- **THEN** the block shows the hero, on every creator page, and the older card is not shown

#### Scenario: Hero entry is skipped when not pending
- **WHEN** the only unseen entry is a hero that is no longer pending (expired or out of audience)
- **THEN** no block renders

#### Scenario: Block respects the preference
- **WHEN** `changelog_cards` is false and an entry is unseen
- **THEN** the response contains no block, and the sidebar still shows the unseen indicator

#### Scenario: Respondent pages never carry the block
- **WHEN** a signed-in creator opens their own survey as a respondent (`/surveys/<id>/…`)
- **THEN** the response contains no block markup

#### Scenario: No banner and no corner card
- **WHEN** any creator page renders for a creator with unseen entries
- **THEN** it contains neither `id="whatsNewHero"` nor `id="whatsNewCard"`

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

On pages that carry the application sidebar, "What's new" SHALL be offered as the sidebar footer
item (with a `wn-dot` when `whats_new.unseen_count` is non-zero) and as the "?" menu item (with a
`wn-badge` carrying the count when it is non-zero), and in the editor's mobile overflow menu as
before. All SHALL link to the page. The header SHALL carry no gift icon there. Pages without the
sidebar keep the pre-change entry points.

#### Scenario: Unseen indicator
- **WHEN** a creator has two unseen entries
- **THEN** the "?" menu item badge reads "2" and the sidebar footer item carries the dot

#### Scenario: All seen
- **WHEN** a creator has no unseen entries
- **THEN** the menu item has no badge and the footer item no dot

#### Scenario: No gift in the header
- **WHEN** a creator opens the dashboard
- **THEN** the header contains no gift icon linking to the What's new page

### Requirement: Changelog events reach PostHog

The system SHALL emit `changelog_card_shown` (browser, guarded by `window.posthog`),
`changelog_card_dismissed` (server, `how`) and `changelog_page_viewed` (server), each with `entry_id`. Server-side
emission SHALL be a no-op when PostHog is unconfigured.

#### Scenario: Dismiss emits
- **WHEN** PostHog is configured and a creator posts `how=close`
- **THEN** `product_events.emit` is called with `changelog_card_dismissed`,
  `{'entry_id': <latest>, 'how': 'close'}`

### Requirement: The changelog is public
`/changelog/` SHALL list every changelog entry, newest first, to any visitor without signing in,
each with its date, New/Fixed tag, title, image and body, and an anchor equal to the entry id.
It SHALL NOT render the editor "Open" links or hero chips. `/changelog/feed.xml` SHALL be an
RSS 2.0 feed of the newest entries, each linking to `/changelog/#<id>` on the public host.

#### Scenario: Anonymous visitor reads the changelog
- **WHEN** an anonymous visitor opens `/changelog/`
- **THEN** the page lists the newest entry first, each inside an element whose id is the entry id

### Requirement: An entry links to the article that expands it
When a published blog article names an entry id in its `changelog` header, that entry SHALL show
a "Read the article" link to `/blog/<slug>/` on `/changelog/` and on `/editor/whats-new/`. A
draft article SHALL NOT produce the link.

#### Scenario: Entry with an article
- **GIVEN** a published article with `changelog: 2026-11-10-budget-questions`
- **WHEN** a creator opens `/editor/whats-new/`
- **THEN** the budget entry links to the article

