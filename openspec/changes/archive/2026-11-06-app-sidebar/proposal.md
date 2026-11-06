## Why

The creator header is one row that holds everything: brand, the gift, "?", language, workspace,
username, Logout (#538). There is no place in it for a second module, and the roadmap adds
surfaces that are not a survey: the analysis and report module (#347), the presentation round
(#349), paper responses (#350), a library of reference layers. The workspace's own pages
(Members, Settings, Plan & billing) and API & connections are entries at the bottom of the
workspace dropdown, and the workspace switcher sits between the language control and the username
as if it were one more preference.

The owner wants one more level — modules — and nothing else redesigned: the dashboard, the
editor's toolbar and tabs, every page body stay as they are.

## What Changes

- **A left sidebar on every creator page**: everything a signed-in creator opens under `/editor/`,
  `/org/` and `/billing/`, from both `base.html` and `editor/editor_base.html`. One partial,
  `partials/_app_sidebar.html`. Sign-in, registration, password reset, the respondent status pages,
  the abuse pages, the invitation landing, the OAuth consent page, `/surveys/` and `/r/` never get it.
- **Contents, top to bottom**: the workspace switcher (logo, workspace name, plan chip, the same
  `org_switch` POST forms and *New workspace*); the modules — today only **Surveys**, from the
  registry `survey/app_nav.py::MODULES`; **Integrations** → *API* (tokens and connected apps) and *MCP* (the
  assistant set-up page), both with `{% pro_badge %}`; **Workspace** → *Members*, *Plan & billing* (owner/admin, as today),
  *General* (name, slug, plan — at the old `org_settings` URL); a footer with *What's new* (unseen dot), *Help centre* (when `HELP_URL` is set) and
  *Collapse*.
- **Two widths**: 256 px on workspace-level pages, a 60-px icon rail inside a survey (an
  `editor_base` page with a `survey` in context), labels as tooltips. *Collapse* on a
  workspace-level page is remembered in `localStorage['msSidebar']`; *Expand* inside a survey lasts
  for the page.
- **Phones (< 768 px)**: an off-canvas drawer behind a ☰ button in the existing header; always the
  full sidebar. The editor's two-level mobile navigation is untouched.
- **The header loses two things and nothing else changes**: the gift icon and the workspace
  dropdown move into the sidebar; the "Mapsurvey" brand hides on desktop (the sidebar carries the
  logo). "?", the language control, the username and Logout stay where they are. The username
  becomes a small menu with what had nowhere else to go: *Preferences* and, on editor pages, *Ask
  before publishing or changing structure*; on phones it also carries the language list and *Help
  & support*, which the removed dropdown used to hold there.
- **The workspace pages lose their own navigation**: the Settings / Members / Plan & billing /
  Dashboard buttons on those pages and the "← Dashboard" link on workspace-level editor pages go
  (the sidebar is the way between them); the workspace name above each section title goes (the
  sidebar shows it). *Settings* is renamed *General* and laid out like Members (it was the sign-in
  page's card); the API page gets the same column and loses the MCP block, which is the MCP page.
- **The Pro trial hero (`2026-10-28-try-pro`) is removed**: the trial starts by itself.
- **Page bodies are otherwise not touched.** The sidebar is `position: fixed`; the page gets
  `padding-left` equal to its width, so every `calc(100vh - 49px)` stays right.
- **One What's new entry** and one browser event, `app_nav_clicked` (item key + surface only).

## Capabilities

### New Capabilities
- `workspace-navigation`: the sidebar, its contents, widths and drawer, the pages it appears on
  and the ones it never does, and what leaves the header.

### Modified Capabilities
- `in-app-changelog`: the "What's new" entry points are the sidebar footer item (dot) and the "?"
  menu (badge); the header gift and the workspace-dropdown item go.
- `creator-preferences-page`: "Preferences" lives in the username menu on creator pages.

## Impact

- New: `survey/app_nav.py`, context processor `app_nav`, `partials/_app_sidebar.html`,
  `partials/_app_user_menu.html`, `css/app_sidebar.css`, `js/app_sidebar.js`,
  `survey/changelog/2026-11-06-app-sidebar.html`, `survey/tests/test_workspace_navigation.py`.
- Edited: `base.html`, `editor/editor_base.html` (sidebar include, body classes, header trimmed
  under `app_nav.show`); the old header renders unchanged where the sidebar does not.
- Catalogs: a handful of new creator strings in every catalog.
- No model, migration, URL or view change. Respondent pages, `/r/`, embeds and the API untouched.
