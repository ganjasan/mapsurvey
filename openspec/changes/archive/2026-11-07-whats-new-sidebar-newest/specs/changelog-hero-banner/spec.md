## MODIFIED Requirements

### Requirement: The hero renders on the dashboard only, and suppresses the small card everywhere
A pending hero SHALL render in the sidebar's *What's new* block (capability `in-app-changelog`)
on every page that carries the sidebar, in place of any OLDER card entry: its picture when set, the
date, the title, one call to action linking to `link` with `link_query` labelled `cta_label`,
*Read more*, × and *Don't show these*. When an unseen card entry is newer than the pending hero,
the block SHALL show that card entry instead: the sidebar shows the newest unseen entry. No banner
SHALL render on the dashboard or anywhere else. The hero SHALL NOT render on respondent surfaces,
for anonymous users, or when `changelog_cards` is off.

#### Scenario: Dashboard shows the hero in the sidebar
- **WHEN** a creator with a pending hero opens `/editor/`
- **THEN** the sidebar block carries the hero's id with tier `hero`, its title and the call to
  action to the resolved `link` plus `link_query`, and no banner markup is in the page

#### Scenario: Other creator pages show the same hero
- **WHEN** the same creator opens a survey editor page
- **THEN** its sidebar block carries the same hero and the page has no small card

#### Scenario: A newer card wins over an older hero
- **WHEN** a card entry shipped after the pending hero is unseen
- **THEN** the sidebar block carries that card entry and not the hero
