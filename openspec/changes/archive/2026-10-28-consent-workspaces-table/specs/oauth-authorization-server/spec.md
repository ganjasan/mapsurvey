## ADDED Requirements

### Requirement: Reachable workspaces are a folded table
The consent page SHALL present the workspaces the grant reaches as a `<details>` element closed by
default. With more than one workspace, its summary SHALL read the number of workspaces and how many
of them hold the `api` feature ("Workspaces: 9 · on Pro: 3"); with exactly one, the summary SHALL name
it and its plan. Opened, it SHALL show a table with one row per workspace — name and plan — ordered
with the workspaces that hold the `api` feature first, then by name. A user with no workspace SHALL
see the existing "not a member of any workspace" sentence instead of the element.

#### Scenario: Many workspaces
- **WHEN** a user with nine workspaces, three of them on Pro, reaches consent
- **THEN** the page shows a closed `<details>` whose summary reads "Workspaces: 9 · on Pro: 3", and its table lists the three Pro workspaces before the six Free ones, each group by name

#### Scenario: One workspace
- **WHEN** a user with one Free workspace named "Test" reaches consent
- **THEN** the summary names "Test" and "Free"

#### Scenario: No workspace
- **WHEN** a user with no membership reaches consent
- **THEN** the page shows "You are not a member of any workspace yet." and no table
