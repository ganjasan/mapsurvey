## Context

Two base templates render creator chrome: `base.html` (the dashboard, the org pages, billing, and
also sign-in, registration, password reset, the respondent status pages and the abuse pages) and
`editor/editor_base.html` (every survey-scoped page plus Preferences, connections, What's new, the
start and create pages, and the OAuth consent page). Both headers are 49 px high and survey layouts
subtract that from `100vh`. `MOBILE_EDITOR_NAV` adds, below 768 px, a top strip of page tabs and a
bottom bar of panes.

The approved mockup is `app-sidebar.mockup.html` next to this file (v2): the sidebar, today's
header without the gift and the workspace dropdown, today's page bodies.

## Goals / Non-Goals

**Goals:** a module level that can grow; the workspace's pages one click away; no page body,
toolbar or tab changes; nothing that is reachable today becomes unreachable.

**Non-Goals:** the modules themselves (each registers a row when it ships); breadcrumbs, a global
search, an avatar menu; respondent and public-results pages; a kill switch (owner rule).

## Decisions

### D1. Fixed sidebar + body padding, not a grid around the page
`.app-sidebar` is `position: fixed; top: 0; bottom: 0; left: 0` and `body.app-has-sidebar` gets
`padding-left: var(--app-side-w)` (256 px, 60 px with `.app-rail`, 0 below 768 px). Every
page keeps its own layout, its sticky navbar and its `calc(100vh - 49px)`: the header row is
still 49 px and still at the top of the remaining width. A grid wrapper would have meant moving
`{% block content %}` of two bases and every full-height page. The sidebar's head is 49 px with a
bottom border so it lines up with the navbar. `z-index: 101` — above the sticky editor navbar
(100), below every overlay and modal (600+, Bootstrap 1040+), so a modal still covers it.

### D2. One registry and one context processor
`survey/app_nav.py` holds `NavItem(key, label, url_name, icon)` rows: `MODULES` (Surveys),
`INTEGRATIONS` (API, MCP) and the workspace rows, `APP_NAV_PREFIXES =
('/editor/', '/org/', '/billing/')`, `shows_sidebar(request)` (authenticated + prefix) and
`active_item(request)` from `resolver_match.url_name` (`org_members*` → members, `org_billing*` →
billing, `org_settings` → settings, `editor_account_connections` → api, `editor_survey_start_agent` → mcp, `whats_new` →
whats_new, `editor_account_preferences` / `org_create` → none, anything else under `/editor/` →
surveys). The context processor `app_nav` returns a lazy `{show, active, modules, plan}`.
Templates never test `request.path`. A module row's `url_name` must resolve (`test_every_module_resolves`).

### D3. What the header loses, under `app_nav.show` only
Where the sidebar shows, `base.html` and `editor_base.html` drop the gift icon and the workspace
dropdown, hide the brand at ≥ 768 px, add a ☰ button (< 768 px), and turn the username into a
dropdown (`partials/_app_user_menu.html`): Preferences; *Ask before publishing or changing
structure* when `editor_page`; then a phones-only block with the language list, *Help & support* /
*Email support* and `billing/_help_entries.html` — what the dropdown carried on phones, where "?"
and the language control are hidden. Where the sidebar does not show, the header renders exactly
as before (the same markup inside `{% else %}` branches). The editor's ⋯ overflow is unchanged.

### D4. Rail inside a survey, expanded elsewhere; the width is the browser's
`editor_base.html` adds `app-rail` to `<body>` when `survey` is in context. On other pages an
inline script right after the sidebar reads `localStorage['msSidebar']` and adds `app-rail` before
first paint; *Collapse* writes it. Inside a survey *Expand* toggles the class for the page only:
the map needs the width, and one expand to read a label should not cost 190 px on every survey
afterwards. After any toggle the script dispatches `resize` so Leaflet maps re-measure. No
server-side preference: a width is a device thing.

### D5. Drawer on phones
Below 768 px the sidebar is translated off-canvas; ☰ adds `app-drawer-open` to `<body>`, a
backdrop closes it, so do Escape and any link inside. The drawer ignores `app-rail`. It sits above
the mobile tab bar and sheets (z-index 1035). Nothing in `editor-mobile.css` or
`editor_mobile_nav.js` changes.

### D6. The plan chip
`PRO` when `billing.entitlements.for_organization(org).is_pro`, `TRIAL` when
`billing.trial.state_for(org, user) == 'live'`, nothing otherwise — computed lazily, the same
sources Plan & billing reads. *API* and *MCP* carry `{% pro_badge active_org "api" False %}` (MCP spends the same allowance)
(the one Pro mark, never hand-written).

### D7. Vocabulary and strings
The sidebar reuses existing catalog strings where they exist (*Surveys*, *Members*, *General*,
*Plan & billing*, *What's new*, *Help centre*) and adds *Workspace*,
*Integrations*, *New workspace*, *Switch workspace*, *Collapse*, *Expand sidebar*, *Menu*,
*Account* — in every catalog (`TranslationCatalogHygieneTest`).

### D8. Analytics
`app_nav_clicked` with `item` (registry key) and `surface` (`sidebar | drawer`), from
`js/app_sidebar.js`, guarded by `window.posthog`. No survey id or name.

### D9. API and MCP are two items (owner, 2026-11-06)
*API* is the former "API & connections" page — personal tokens and connected apps — under the
workspace pages' layout. *MCP* is the assistant set-up page (`editor_survey_start_agent`) the
start page already links to; the sidebar opens it with `?from=sidebar`, which drops its back link,
and it now carries the set-up guide and tool reference links the API page's MCP block had. Item
rows can be role-gated (`NavItem.roles`) because that page needs the editor role.

## Risks / Trade-offs

- **Fixed elements anchored at `left: 0` on desktop** would slide under the sidebar → none exist on
  creator pages at ≥ 768 px today (checked: `paper_review.css` belongs to the operator entry form,
  which is a respondent template; the rest are phone-only or centred).
- **Two header variants per base** (with and without the sidebar) → the old one is the untouched
  `{% else %}` branch; `test_old_header_where_no_sidebar` pins sign-in and `survey_thanks`.
- **Language on phones moves from the workspace dropdown to the username menu** → same partial,
  same place in the header.
