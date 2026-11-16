## MODIFIED Requirements

### Requirement: Prev/next triage within the current list
The detail surface SHALL offer previous/next navigation iterating the session list as currently
filtered and sorted at the moment the surface was opened. When the underlying list changes while
the surface is open, navigation SHALL continue over the opened snapshot and the surface SHALL
indicate that the list has changed.

#### Scenario: Next follows the filtered order
- **WHEN** the table is filtered to "Required unanswered" and the drawer is opened on the first
  listed session
- **THEN** "next" opens the following listed session in the table's sort order

#### Scenario: List changes underneath
- **WHEN** a live refresh adds sessions while the drawer is open
- **THEN** prev/next still traverse the snapshot and a "list changed" hint is shown
