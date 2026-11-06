# workspace-navigation Specification

## Purpose
The application sidebar on creator pages: the workspace switcher, the modules, the integrations and the workspace's own pages, in two widths and a phone drawer, and what the header and the workspace pages gave up for it.
## Requirements
### Requirement: A sidebar on every creator page
The system SHALL render one application sidebar, from one partial, on every page a signed-in
creator opens under `/editor/`, `/org/` and `/billing/`, whether the page extends `base.html` or
`editor/editor_base.html`. It SHALL NOT render for an anonymous visitor, nor on any other path
(sign-in, registration, password reset, `/surveys/…` including the respondent status pages,
`/r/…`, `/oauth/…`, the abuse pages, the invitation landing), whatever template those pages extend.

#### Scenario: Dashboard and editor share the sidebar
- **WHEN** a creator opens the dashboard and then a survey's Build page
- **THEN** both pages carry the sidebar with the same items in the same order

#### Scenario: Respondent page while signed in
- **WHEN** a signed-in creator opens a page under `/surveys/`
- **THEN** the page carries no sidebar

#### Scenario: Sign-in page
- **WHEN** a visitor who is not signed in opens the sign-in page
- **THEN** the page carries the pre-change header and no sidebar

### Requirement: Sidebar contents and order
The sidebar SHALL contain, top to bottom: the workspace switcher (active workspace name, a plan
chip, the creator's workspaces as `org_switch` POST controls, *New workspace*); the modules from
the registry `survey/app_nav.py::MODULES`, today only *Surveys*; an *Integrations* group with
*API* (personal tokens and connected apps) and *MCP* (the assistant set-up page, editor role
and up), both carrying the `api` Pro mark; a *Library* group with *Map styles* (the workspace's
map style library at the `org_map_styles` URL, every member), carrying the `map_styles` Pro mark;
a *Workspace* group with *Members*, *Plan &
billing* (owner and admin only) and *General* (name, slug and plan, at the `org_settings` URL); and a footer with *What's new* (a dot when
`whats_new.unseen_count` is non-zero), *Help centre* when `HELP_URL` is set, and *Collapse*. The
item for the current page SHALL be marked active, resolved from the URL name by
`app_nav.active_item`. No item SHALL be rendered for a module that does not exist yet.

#### Scenario: Active item follows the page
- **WHEN** a creator opens `/org/<slug>/members/`
- **THEN** *Members* is the active item and *Surveys* is not

#### Scenario: Survey pages activate Surveys
- **WHEN** a creator opens a survey's Responses page
- **THEN** *Surveys* is the active item

#### Scenario: Plan & billing for owners only
- **WHEN** a workspace member with the `editor` role opens the dashboard
- **THEN** the sidebar has no *Plan & billing* item

#### Scenario: Map styles for every member
- **WHEN** a workspace member with the `viewer` role opens the dashboard
- **THEN** the sidebar has a *Map styles* item under *Library* carrying the `map_styles` Pro mark, and opening it marks that item active

#### Scenario: Plan chip reads the entitlement
- **WHEN** the active workspace has a live Pro subscription
- **THEN** the workspace row shows `PRO`; on a Free workspace with a live trial it shows `TRIAL`; on a Free workspace without one it shows nothing

#### Scenario: Registry URLs resolve
- **WHEN** a module row names a URL name that does not resolve
- **THEN** `test_every_module_resolves` fails

### Requirement: The header loses only what moved
On pages that carry the sidebar the header SHALL NOT show the gift icon or the workspace dropdown,
and SHALL keep "?" (`help-nav-icon`), the language control, the username and Logout where they
were. The username SHALL open a menu with *Preferences*, on editor pages *Ask before publishing or
changing structure*, and below 768 px the language list and *Help & support*. Pages without the
sidebar SHALL render the pre-change header unchanged. Page bodies, the editor toolbar and its ⋯
overflow SHALL be unchanged.

#### Scenario: Dashboard header
- **WHEN** a creator opens the dashboard
- **THEN** the header has no gift link to What's new and no `fa-building` dropdown, and has `help-nav-icon`, the language control and a Logout POST form

#### Scenario: Workspace pages carry no second navigation
- **WHEN** an owner opens Plan & billing, Members, General or the advice page of their workspace
- **THEN** the page has no General / Members / Plan & billing / Dashboard buttons or links of its own; the sidebar is the way between them

#### Scenario: API and MCP are two items
- **WHEN** an owner opens the dashboard
- **THEN** *API* links to `/editor/account/connections/` and *MCP* to `/editor/surveys/start/agent/?from=sidebar`; a viewer sees no *MCP* item

#### Scenario: MCP opened from the sidebar has no way back
- **WHEN** a creator opens the MCP item
- **THEN** the page shows no "← Ways to start" or "← Dashboard" link; opened from Ways to start it keeps "← Ways to start"

#### Scenario: Workspace-level editor pages carry no Dashboard link
- **WHEN** a creator opens the API page, Preferences or What's new
- **THEN** the editor navbar has no "← Dashboard" link and no page title of its own; a survey page keeps "← Dashboard"

#### Scenario: Username menu
- **WHEN** a creator opens the username menu on a survey page
- **THEN** it lists Preferences and the confirmation toggle

### Requirement: Two widths, the rail inside a survey
The sidebar SHALL render expanded on workspace-level pages and as an icon rail (labels as hover
tooltips and accessible names) on every `editor_base` page with a survey in context. On a
workspace-level page *Collapse* / *Expand* SHALL persist in `localStorage['msSidebar']` and be
applied before first paint. Inside a survey *Expand* SHALL last for that page only.

#### Scenario: Survey page opens as a rail
- **WHEN** a creator opens a survey's Build page
- **THEN** `body` carries the `app-rail` class

#### Scenario: Dashboard opens expanded
- **WHEN** a creator who never collapsed the sidebar opens the dashboard
- **THEN** `body` does not carry `app-rail`

### Requirement: A drawer below 768 px
Below 768 px the sidebar SHALL be an off-canvas drawer opened by a ☰ control in the header and
closed by its backdrop, Escape, or a navigation. The drawer SHALL always be the full sidebar. The
editor's two-level mobile navigation SHALL be unchanged.

#### Scenario: Drawer on a phone
- **WHEN** a creator opens the dashboard at 390 px and taps ☰
- **THEN** the full sidebar slides in over the page with a backdrop; tapping the backdrop closes it

### Requirement: Navigation clicks are measured by key only
Clicking a sidebar item SHALL emit the browser event `app_nav_clicked` with `item` (the registry
key) and `surface` (`sidebar | drawer`), guarded by `window.posthog`, and nothing else.

#### Scenario: Event payload
- **WHEN** a creator clicks *Members* in the sidebar on a desktop
- **THEN** `app_nav_clicked` carries `item: "members"` and `surface: "sidebar"` only

