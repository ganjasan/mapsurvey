## Why

Data (epic #676) and Reports (epic #712) are new modules that will keep changing after they ship. The
sidebar lists them next to Surveys with nothing that says so (owner, 2026-11-17).

## What Changes

- The sidebar rows of Data and Reports carry a small "β" beside the label, with the tooltip "Beta".
- Which rows are beta is a field of the navigation registry (`NavItem.beta`), so taking the mark off a
  module is one word there.
- The mark is not shown in the icon rail.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `workspace-navigation`: a new requirement — modules in beta are marked in the sidebar.

## Impact

- `survey/app_nav.py`, `survey/templates/partials/_app_sidebar.html`, `survey/assets/css/app_sidebar.css`.
- `survey/tests/test_workspace_navigation.py`.
