## MODIFIED Requirements

### Requirement: The export dialog states every choice before the download starts

The Responses page (v2 and legacy dashboards) and the survey card "..." menu SHALL open one export
dialog instead of downloading directly. The dialog SHALL offer: a format (one radio per available
format with a one-line description naming the tool it serves), the version scope as a one-line field
that names what is ticked and opens a panel with a search box, an "All versions" check-box that
ticks or clears them all, and one check-box per version (hidden when the survey has a single
version; "Draft (test)", where offered, is exclusive of the others), and three
switches — "Include excluded responses" (off), "Completed responses only" (off) and "Include
attached files" (off, present only when the survey has file questions). Its primary action SHALL
navigate the browser to a `GET /surveys/<uuid>/download` URL that encodes the choices, so the export
is a copyable link; several ticked versions SHALL travel as one comma-separated `version` value,
every version ticked SHALL send no `version` at all, and with no version ticked the primary action
SHALL be disabled. The last chosen format SHALL be remembered per browser.

#### Scenario: Dialog builds a link, not a request
- **WHEN** a creator picks Excel, "Completed responses only" and version v2 and presses Export
- **THEN** the browser navigates to `/surveys/<uuid>/download?format=xlsx&version=v2&completed_only=1`

#### Scenario: Several versions in one link
- **WHEN** a creator ticks v10 and v11 of an eleven-version survey and picks Excel
- **THEN** the Export link is `/surveys/<uuid>/download?format=xlsx&version=v11,v10`

#### Scenario: All versions is the shortcut
- **WHEN** the creator ticks "All versions", or ticks every version one by one
- **THEN** every version check-box is ticked and the link carries no `version` parameter

#### Scenario: Dozens of versions stay one line
- **WHEN** a survey has 50 versions and the creator types `4` into the panel's search box
- **THEN** the closed field still takes one line, and the panel lists only the versions whose label
  contains `4`

#### Scenario: Nothing ticked
- **WHEN** the creator clears every version check-box
- **THEN** the Export button is disabled until a version is ticked again

#### Scenario: Single-version survey hides the version field
- **WHEN** the survey has no archived versions
- **THEN** the dialog shows no version selector and the URL carries no `version` parameter

#### Scenario: Attached-files switch only when there is something to attach
- **WHEN** the survey has no `photo`, `audio` or `document` question
- **THEN** the "Include attached files" switch is absent from the dialog

#### Scenario: GIS formats absent without ogr2ogr
- **WHEN** the `ogr2ogr` binary is not on the host
- **THEN** GeoPackage, Shapefile and KML are not offered and Excel, CSV and the GeoJSON+CSV archive
  still are
