## ADDED Requirements

### Requirement: The module is called Sites
Every creator surface SHALL name the module **Sites** and the object a **site**: the sidebar item, the list page, the builder, the publish popover, the Pro offer, the help page and the changelog. Editor addresses SHALL live under `/editor/sites/`; the public address SHALL stay `/p/<slug>/`. Text about what is drawn on the canvas MAY keep "page" (for example "Blocks on the page"). The marketing site's "landing pages" (SEO landings) are a different thing and SHALL keep their names.

#### Scenario: Sidebar and list
- **WHEN** a member of a Pro workspace opens the editor
- **THEN** the sidebar shows "Sites" linking to `/editor/sites/`, and the list page offers "New site"

#### Scenario: Old editor address
- **WHEN** someone requests `/editor/landings/`
- **THEN** the answer is 404: the old address never shipped
