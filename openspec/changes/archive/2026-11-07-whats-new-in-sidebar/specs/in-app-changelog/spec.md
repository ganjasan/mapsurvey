## MODIFIED Requirements

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
