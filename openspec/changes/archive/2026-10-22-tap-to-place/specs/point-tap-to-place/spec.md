## ADDED Requirements

### Requirement: Tap-to-place setting on point questions
A `point` question SHALL carry a boolean setting `tap_to_place` ("A tap on the map places a mark"), default off. The setting SHALL be offered in the editor only for top-level `point` questions; for every other type it SHALL be stored as off whatever is posted.

#### Scenario: Default is off
- **WHEN** a creator adds a new point question without touching the switch
- **THEN** `tap_to_place` is false and the respondent page behaves exactly as before this change

#### Scenario: Not offered for drawing types
- **WHEN** a creator saves a `line`, `polygon` or `spraycan` question with `tap_to_place=on` in the POST
- **THEN** the stored value is false

### Requirement: Setting honoured only for the only geo question on the section
The setting SHALL take effect only while the question is the only top-level geo question (`point`, `line`, `polygon`, `spraycan`) in its section. One server-side helper SHALL decide this, and the editor badge and the respondent page SHALL both use it.

#### Scenario: Second geo question disables it
- **WHEN** a section has a point question with `tap_to_place` on and a second geo question of any geo type is added to the same section
- **THEN** a map click on the respondent page places nothing, and the editor shows the question's "tap to place" badge greyed out with the reason "Another map question is on this page"

#### Scenario: Sub-questions and non-geo questions do not count
- **WHEN** the section's other questions are text/choice questions or sub-questions of the point question
- **THEN** the setting is in effect

### Requirement: Map click places the mark
While the setting is in effect, a click or tap on the respondent map SHALL create a point feature for the question at the clicked location. The feature SHALL go through the same path as the button + crosshair *Apply*: same marker icon and colour, same sub-question pop-up, same counting toward `min_features`/`max_features` and `required`. The draw button SHALL keep working unchanged.

#### Scenario: Click creates feature and opens its pop-up
- **WHEN** the respondent clicks an empty part of the map on a section whose only geo question is a point question with `tap_to_place` on and sub-questions
- **THEN** a marker appears at the clicked point and its sub-question pop-up opens

#### Scenario: Required satisfied by a tapped mark
- **WHEN** the point question is required and the respondent placed its only mark by tapping the map
- **THEN** the section submits without the "required" warning and the answer is stored like a button-placed one

### Requirement: Clicks that must not place a mark
A map click SHALL NOT place a mark in any of these cases:
- the click is on a marker, pop-up, map control or interactive layer object;
- a draw, crosshair, spray or edit mode is active;
- a pop-up is open when the click starts (that click only closes it);
- the question has reached its `max_features`;
- the question is hidden by a visibility rule;
- the click is part of a double-click or double-tap.

A drag or pan SHALL never place a mark.

#### Scenario: Cap reached
- **WHEN** the question has `max_features` 1 and already has a mark, and the respondent clicks the map
- **THEN** no second mark is created

#### Scenario: Double-tap zoom
- **WHEN** the respondent double-clicks or double-taps the map to zoom
- **THEN** the map zooms and no mark is created

#### Scenario: Click closes an open pop-up
- **WHEN** a mark's pop-up is open and the respondent clicks elsewhere on the map
- **THEN** the pop-up closes and no new mark is created

#### Scenario: Setting off
- **WHEN** `tap_to_place` is off
- **THEN** a map click does nothing, as before this change

### Requirement: Respondent hint
While the setting is in effect, the respondent panel SHALL show the hint "Tap the map to mark a place — or use the button." under the question's draw button.

#### Scenario: Hint shown only when in effect
- **WHEN** the setting is on but a second geo question shares the section
- **THEN** the hint is not rendered

### Requirement: Editor control and badge
The point question settings SHALL show a switch labelled "A tap on the map places a mark", with the note "Works only while this is the only map question on its page". The question row in the section list SHALL show a "tap to place" badge when the setting is on. The badge SHALL be greyed out, with the reason in its tooltip, when the setting is not in effect.

#### Scenario: Badge in effect
- **WHEN** the setting is on and the question is the only geo question in its section
- **THEN** the row shows an active "tap to place" badge

### Requirement: Setting travels with the survey
`tap_to_place` SHALL survive ZIP export and import, question duplication, copy/paste and the draft copy of a live survey. An archive without the key SHALL import it as off. AI-generated drafts SHALL create it as off. On a published survey, changing it SHALL be a safe edit made in place, never a structural one.

#### Scenario: ZIP round trip
- **WHEN** a survey with a `tap_to_place` point question is exported and re-imported
- **THEN** the imported question has `tap_to_place` true

#### Scenario: Old archive
- **WHEN** an archive whose questions have no `tap_to_place` key is imported
- **THEN** every imported question has `tap_to_place` false

#### Scenario: Live survey edit
- **WHEN** a creator toggles the switch on a published survey's point question
- **THEN** the change is saved in place without creating unpublished changes
