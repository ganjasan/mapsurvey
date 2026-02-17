## ADDED Requirements

### Requirement: Version-aware download dropdown in editor dashboard

The editor dashboard SHALL display a dropdown menu for "Download Data" when a survey has more than one version. The dropdown SHALL offer options to download data for specific versions or all versions.

For surveys with only one version (no archived history), the system SHALL display a plain "Download Data" link pointing to the latest version (current behavior).

#### Scenario: Survey with single version shows plain link
- **WHEN** a survey has `version_number=1` and no archived versions
- **THEN** the dashboard displays a plain "Download Data" link to `/surveys/<uuid>/download`

#### Scenario: Survey with multiple versions shows dropdown
- **WHEN** a survey has `version_number > 1` (archived versions exist)
- **THEN** the dashboard displays a "Download Data" dropdown with options:
  - "All Versions" linking to `?version=all`
  - "Current (vN)" linking to `?version=latest` where N is the current version number
  - One entry per archived version "vM" linking to `?version=vM` in descending order

#### Scenario: Archived versions are prefetched efficiently
- **WHEN** the editor dashboard loads a list of surveys
- **THEN** the archived versions for all surveys SHALL be loaded in a single batched query (no N+1)
