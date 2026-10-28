## MODIFIED Requirements

### Requirement: New-user redirect to survey creation
The `/editor/` dashboard SHALL redirect users whose active organization has zero
canonical, non-deleted surveys — and whose role permits creating surveys — to
`/editor/surveys/new/?welcome=1`. The redirect SHALL be suppressed by the query parameter
`dashboard=1`; the create page SHALL expose a "Skip to dashboard" escape link carrying
that parameter, its Cancel link SHALL carry it as well, and the editor navbar's
"Dashboard" link SHALL carry it too, so no link reachable from the create page can
redirect back to it.

#### Scenario: Empty org lands on create page
- **WHEN** an editor-or-higher user with no surveys in the active org opens `/editor/`
- **THEN** they are redirected to `/editor/surveys/new/?welcome=1` and the page shows a "Skip to dashboard" link

#### Scenario: Explicit dashboard access
- **WHEN** the same user opens `/editor/?dashboard=1`
- **THEN** the dashboard renders (empty state) without redirecting

#### Scenario: Navbar Dashboard link does not loop
- **WHEN** the same user clicks "Dashboard" in the editor navbar on the create page
- **THEN** the dashboard renders (HTTP 200) instead of redirecting back to the create page
