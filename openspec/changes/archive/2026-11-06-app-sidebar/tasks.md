## 1. Registry and context

- [x] 1.1 `survey/app_nav.py`: `NavItem`, `MODULES`, `INTEGRATIONS`, `WORKSPACE`, `APP_NAV_PREFIXES`, `shows_sidebar`, `active_item`, `plan_chip`
- [x] 1.2 Context processor `survey.context_processors.app_nav` (lazy), registered in settings

## 2. Partials, styles, script

- [x] 2.1 `partials/_app_sidebar.html`: workspace switcher (plan chip, `org_switch` forms, New workspace), modules, Integrations (`pro_badge` api), Workspace (Plan & billing for owner/admin), footer (What's new + `wn-dot`, Help centre, Collapse); `data-nav-key`, `aria-label` on every item; backdrop; pre-paint script
- [x] 2.2 `partials/_app_user_menu.html`: username dropdown — Preferences, confirm toggle (`editor_page`), phones-only language list + Help & support + help entries
- [x] 2.3 `css/app_sidebar.css`: fixed sidebar, body padding, rail, tooltips, drawer < 768 px, ☰ button, brand hidden ≥ 768 px
- [x] 2.4 `js/app_sidebar.js`: Collapse/Expand (localStorage off survey pages, resize dispatch), drawer open/close (backdrop, Escape, link click), `app_nav_clicked`

## 3. The two bases

- [x] 3.1 `base.html`: under `app_nav.show` — sidebar include, body classes, ☰, brand class, no gift, no workspace dropdown, username menu; `{% else %}` the old header unchanged
- [x] 3.2 `editor/editor_base.html`: the same; `app-rail` on `<body>` when `survey`; ⋯ overflow unchanged

## 4. Strings and changelog

- [x] 4.1 New strings in every catalog, compile `.mo`
- [x] 4.2 `survey/changelog/2026-11-06-app-sidebar.html`

## 5. Tests (`survey/tests/test_workspace_navigation.py`)

- [x] 5.1 Sidebar on dashboard, Members, Plan & billing, Preferences, connections, Build, Responses; not on sign-in, `/surveys/…`, anonymous
- [x] 5.2 Active item per page; `test_every_module_resolves`; Plan & billing hidden for an editor
- [x] 5.3 Plan chip: Pro / trial / Free
- [x] 5.4 Header: no `wn-nav-icon`, no `fa-building`; `help-nav-icon`, Logout POST, Preferences in the username menu; old header on sign-in
- [x] 5.5 `app-rail` on survey pages, not on the dashboard
- [x] 5.6 Adjust existing tests that read the old header (`test_in_app_changelog` dot/badge); run the related modules + `test_ui_internationalization` + `test_test_suite`

## 6. Verify

- [x] 6.1 Local stand at 1440 and 390 px: dashboard, Members, Build, Responses map, drawer — screenshots against the mockup
