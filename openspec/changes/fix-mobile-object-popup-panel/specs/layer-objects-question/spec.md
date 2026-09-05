## ADDED Requirements

### Requirement: Opening an object on a phone reveals the map
On a mobile viewport (the panel overlays the map), opening an object from the list SHALL
hide the panel before the popup opens and SHALL show it again when that popup closes.
Desktop behaviour SHALL be unchanged.

#### Scenario: Tap a mark in the list on a phone
- **WHEN** a respondent on a 390 px viewport taps a mark row
- **THEN** the panel slides away, the map flies to the mark and its popup is fully visible

#### Scenario: Close the popup
- **WHEN** the respondent closes that popup
- **THEN** the panel returns with the list
