# Version Export UI Specification

## Purpose
The version-aware download control in the editor dashboard, which lets a creator export a specific version of a survey rather than only the current one.

## Requirements
### Requirement: Version-aware download dropdown in editor dashboard

The editor dashboard SHALL offer "Export data" in each survey card's "..." menu. The entry SHALL
open the export dialog (spec `responses-export-formats`) for that survey; when the survey has more
than one version the dialog's version selector SHALL list "All Versions", "Current (vN)" and one
entry per archived version "vM" in descending order, preselected to "All Versions". For a survey
with a single version the dialog SHALL show no version selector. The menu SHALL no longer contain
direct per-version download links or a separate "incl. excluded" group: both choices live in the
dialog. The survey definition backup group SHALL read "Backup (survey file)".

#### Scenario: Survey with single version opens the dialog without a version field
- **WHEN** a survey has `version_number=1` and no archived versions and the creator picks
  "Export data" in its card menu
- **THEN** the export dialog opens for that survey with no version selector, and the URL it builds
  carries no `version` parameter

#### Scenario: Survey with multiple versions lists them in the dialog
- **WHEN** a survey has `version_number > 1` (archived versions exist) and the creator picks
  "Export data" in its card menu
- **THEN** the export dialog's version selector offers:
  - "All Versions" (`version=all`), selected
  - "Current (vN)" (`version=latest`) where N is the current version number
  - One entry per archived version "vM" (`version=vM`) in descending order

#### Scenario: Archived versions are prefetched efficiently
- **WHEN** the editor dashboard loads a list of surveys
- **THEN** the archived versions for all surveys SHALL be loaded in a single batched query (no N+1)

#### Scenario: Backup group is named apart from the data export
- **WHEN** a creator opens a survey card's "..." menu
- **THEN** the `export_survey` links sit under a "Backup (survey file)" heading with a hint that
  it is the import format, below the "Export data" entry
