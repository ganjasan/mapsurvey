## ADDED Requirements

### Requirement: Inline map position pickers open locked
The survey default map position picker on the settings page and in the in-editor settings panel SHALL open locked, with every pointer, touch and keyboard way of moving the map switched off. A "Change position" button on the map, or a click anywhere on the locked map, SHALL unlock it. An unlocked map SHALL show a "Done" button and SHALL lock again on that button, on a press outside the map, and when the map leaves the viewport.

#### Scenario: Scrolling over the map changes nothing
- **WHEN** a creator opens the settings page of a survey positioned at (59.437, 24.7536) zoom 12 and scrolls the page with the mouse wheel while the pointer is over the map
- **THEN** the page scrolls, the map stays at (59.437, 24.7536) zoom 12, and no request is sent to the map-position endpoint

#### Scenario: Dragging a locked map changes nothing
- **WHEN** a creator drags across the map without pressing "Change position" first
- **THEN** the map does not move during that gesture and nothing is saved

#### Scenario: Unlock, then move
- **WHEN** a creator presses "Change position", drags the map and stops
- **THEN** the new centre and zoom are saved automatically and the map shows "Done"

#### Scenario: The map locks again by itself
- **WHEN** a creator presses "Change position", moves the map, then clicks into another settings field
- **THEN** the move is saved, the map is locked again and shows "Change position"

#### Scenario: Search moves a locked map
- **WHEN** a creator chooses a place-search result while the map is locked
- **THEN** the map centres on the result, the position is saved, and the map stays locked

#### Scenario: The section modal is not locked
- **WHEN** a creator opens the section map picker modal
- **THEN** the map can be dragged at once, with no "Change position" button
