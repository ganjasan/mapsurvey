## ADDED Requirements

### Requirement: Minimal survey creation
The Create New Survey page SHALL ask only for the survey name and the survey
area (map position picker with creator auto-geolocation and the
auto-center-on-respondent toggle). All other survey configuration (redirect
URL, available languages, visibility, thanks page, cover image, basemaps)
SHALL NOT appear on the creation form; a newly created survey SHALL receive
the model defaults for those fields, and the page SHALL point the creator to
the Survey settings panel for them.

#### Scenario: Create with name only
- **WHEN** a creator submits the form with just a name (map untouched)
- **THEN** the survey is created with default settings (private visibility,
  `#` redirect, all basemaps enabled, empty thanks/languages) and the creator
  lands in the Build space

#### Scenario: Create with name and map position
- **WHEN** a creator clicks a point on the map picker before submitting
- **THEN** the created survey stores that start position and zoom, and the
  auto-center toggle value

#### Scenario: Full settings remain editable after creation
- **WHEN** the creator opens the Survey settings panel of the new survey
- **THEN** all the fields absent from the creation form are present and
  editable there
