# survey-editor Specification (delta)

## ADDED Requirements

### Requirement: The survey nav's dropdowns work on every page that renders it
Any editor page that includes the survey nav tabs SHALL also load the script defining the nav's
dropdown handler. A page that renders the nav without it presents Share and Preview buttons that
throw `ReferenceError` and open nothing. This SHALL hold under both states of the
`MOBILE_EDITOR_NAV` kill switch, since its off state is the rollback path and is exactly the state
in which those dropdowns render on every tab.

#### Scenario: Share page dropdowns open
- **WHEN** the Share page is rendered with `MOBILE_EDITOR_NAV` off
- **THEN** the nav's dropdown handler is defined on the page, not only referenced

#### Scenario: Settings page dropdowns open
- **WHEN** the survey Settings page is rendered with `MOBILE_EDITOR_NAV` off
- **THEN** the nav's dropdown handler is defined on the page, not only referenced
