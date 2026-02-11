## ADDED Requirements

### Requirement: Unique popup form identity
Each map feature's popup form SHALL have a unique `id` attribute derived from the Leaflet layer's internal stamp (`L.Util.stamp(layer)`). The format SHALL be `subquestion_form_<stamp>`.

#### Scenario: New marker gets unique form ID
- **WHEN** a marker is created via `draw:created`
- **THEN** the popup HTML SHALL contain `id="subquestion_form_<stamp>"` where `<stamp>` is the layer's Leaflet ID

#### Scenario: Restored marker gets unique form ID
- **WHEN** a marker is restored from `existingGeoAnswers`
- **THEN** the popup HTML SHALL contain `id="subquestion_form_<stamp>"` using the restored layer's Leaflet ID

#### Scenario: No duplicate form IDs on the page
- **WHEN** multiple markers exist on the map simultaneously
- **THEN** each popup's form element SHALL have a distinct `id` attribute

### Requirement: Popup-scoped property serialization
When saving sub-question answers from a popup, the system SHALL serialize form data from the specific popup's form element, not from a global DOM query.

#### Scenario: Apply button saves correct form data
- **WHEN** the user clicks the "Apply" button in a marker's popup
- **THEN** the system SHALL serialize the form identified by `subquestion_form_<stamp>` for that specific layer

#### Scenario: Popup close saves correct form data
- **WHEN** a popup closes (via `onPopupClose`)
- **THEN** the system SHALL serialize the form from the closing popup's own container, not from a global `$('#subquestion_form')` query

#### Scenario: Multiple markers preserve independent data
- **WHEN** marker A has property `name=["Cafe"]` and marker B has property `name=["Shop"]`, and the user opens marker B's popup then closes it
- **THEN** marker A's properties SHALL remain `name=["Cafe"]` (unchanged) and marker B's properties SHALL reflect the form data from marker B's popup

### Requirement: Popup-scoped property restoration
When a popup opens, sub-question form fields SHALL be populated from the specific layer's `feature.properties`, querying only within the popup's own DOM.

#### Scenario: Opening popup restores that layer's properties
- **WHEN** the user opens a popup on a marker with saved properties
- **THEN** the form fields within that popup SHALL be populated from `this.feature.properties`, and form fields in other (closed) popups SHALL NOT be affected

### Requirement: Popup button handlers scoped to layer
The Apply, Edit, and Delete button click handlers inside a popup SHALL operate on the correct layer, not on a stale closure or global reference.

#### Scenario: Delete button removes correct layer
- **WHEN** the user clicks "Delete" in a marker's popup
- **THEN** the layer associated with that popup SHALL be removed from `editableLayers`

#### Scenario: Edit button edits correct layer
- **WHEN** the user clicks "Edit" in a marker's popup
- **THEN** `startEditMode` SHALL be called with the layer that owns the popup
