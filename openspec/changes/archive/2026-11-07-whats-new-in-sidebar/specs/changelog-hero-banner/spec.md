## MODIFIED Requirements

### Requirement: The hero renders on the dashboard only, and suppresses the small card everywhere
A pending hero SHALL render in the sidebar's *What's new* block (capability `in-app-changelog`)
on every page that carries the sidebar, in place of any card entry: its picture when set, the
date, the title, one call to action linking to `link` with `link_query` labelled `cta_label`,
*Read more*, × and *Don't show these*. No banner SHALL render on the dashboard or anywhere else.
The hero SHALL NOT render on respondent surfaces, for anonymous users, or when
`changelog_cards` is off.

#### Scenario: Dashboard shows the hero in the sidebar
- **WHEN** a creator with a pending hero opens `/editor/`
- **THEN** the sidebar block carries the hero's id with tier `hero`, its title and the call to
  action to the resolved `link` plus `link_query`, and no banner markup is in the page

#### Scenario: Other creator pages show the same hero
- **WHEN** the same creator opens a survey editor page
- **THEN** its sidebar block carries the same hero and the page has no small card

## REMOVED Requirements

### Requirement: Chips name the creator's own surveys
**Reason**: chips were part of the dashboard banner, which is removed; the sidebar block carries a title and one link.
**Migration**: entry files keep their `chips` key (still parsed); nothing renders it.
