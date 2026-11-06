## MODIFIED Requirements

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
