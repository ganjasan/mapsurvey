## MODIFIED Requirements

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
