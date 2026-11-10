## MODIFIED Requirements

### Requirement: Sidebar contents and order
The sidebar SHALL contain, top to bottom: the workspace switcher (active workspace name, a plan
chip, the creator's workspaces as `org_switch` POST controls, *New workspace*); the modules from
the registry `survey/app_nav.py::MODULES`; an *Integrations* group with
*API* (personal tokens and connected apps) and *MCP* (the assistant set-up page, editor role
and up), both carrying the `api` navigation Pro mark; a *Library* group with *Map styles* (the workspace's
map style library at the `org_map_styles` URL, every member), carrying the `map_styles` navigation Pro mark;
a *Workspace* group with *Members*, *Plan &
billing* (owner and admin only) and *General* (name, slug and plan, at the `org_settings` URL); and a footer with *What's new* (a dot when
`whats_new.unseen_count` is non-zero), *Help centre* when `HELP_URL` is set, and *Collapse*. A
module row naming a Pro feature carries that feature's navigation Pro mark. The navigation Pro
mark is `{% pro_nav_mark %}`: nothing unless the workspace is `locked` for the feature, then a
lock without the word "Pro" — a sidebar item never says "Pro", "free to try" or "trial". The
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
- **THEN** the sidebar has a *Map styles* item under *Library*, and opening it marks that item active

#### Scenario: No Pro label in the sidebar of a workspace that can use the features
- **WHEN** the dashboard renders for a Pro workspace, a Free workspace with a live trial, and a Free workspace whose first Pro use would start the trial
- **THEN** no sidebar item carries a Pro mark of any state

#### Scenario: A lock where the feature is out of reach
- **WHEN** the dashboard renders for a Free workspace whose owner used their trial elsewhere
- **THEN** Sites, API, MCP and Map styles each carry a lock icon with the tooltip "A Pro feature. See Plan & billing." and no "Pro" text

#### Scenario: Plan chip reads the entitlement
- **WHEN** the active workspace has a live Pro subscription
- **THEN** the workspace row shows `PRO`; on a Free workspace with a live trial it shows `TRIAL`; on a Free workspace without one it shows nothing

#### Scenario: Registry URLs resolve
- **WHEN** a module row names a URL name that does not resolve
- **THEN** `test_every_module_resolves` fails

### Requirement: Two widths, the rail inside a survey
The sidebar SHALL render expanded on workspace-level pages and as an icon rail (labels as hover
tooltips and accessible names) on every `editor_base` page with a survey in context. While the
active workspace has no surveys — a creator who has just registered, before their first survey
exists — workspace-level pages SHALL also open as the rail (`app_nav.onboarding`), so nothing in
the navigation competes with the start page; an explicit *Expand* the creator made
(`localStorage['msSidebar'] = 'wide'`) wins. On a workspace-level page *Collapse* / *Expand* SHALL
persist in `localStorage['msSidebar']` and be applied before first paint. Inside a survey
*Expand* SHALL last for that page only.

#### Scenario: Survey page opens as a rail
- **WHEN** a creator opens a survey's Build page
- **THEN** `body` carries the `app-rail` class

#### Scenario: Dashboard opens expanded
- **WHEN** a creator who never collapsed the sidebar opens the dashboard of a workspace that has surveys
- **THEN** `body` does not carry `app-rail`

#### Scenario: A new creator starts with the rail
- **WHEN** a creator whose active workspace has no surveys opens the start page or the dashboard
- **THEN** the page marks the sidebar for the rail before first paint (`data-onboarding="1"` on the sidebar, read by the partial's inline script), unless `localStorage['msSidebar']` is `wide`

#### Scenario: The rail ends with the first survey
- **WHEN** the same creator opens the dashboard after their first survey exists
- **THEN** the sidebar is not marked for onboarding
