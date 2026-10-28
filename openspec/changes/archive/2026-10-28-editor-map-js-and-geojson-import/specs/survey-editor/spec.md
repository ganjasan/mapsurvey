## ADDED Requirements

### Requirement: Map position autosave survives its panel being replaced

A pending save SHALL be cancelled when its picker's container is removed, so nothing
fires against a detached DOM. If a save is nevertheless attempted and the fields it needs
cannot be read, it SHALL be abandoned rather than sent with a substituted value: posting a
default for a control the creator never touched would persist a choice they did not make.
Neither path SHALL raise.

The pickers save after a debounce pause, and the editor's settings panel is an HTMX
fragment that can be swapped away before that pause elapses; when it is, the elements the
pending save reads are gone.

#### Scenario: The panel is swapped away mid-pause

- **WHEN** a creator moves the map and navigates to another editor page before the debounce elapses
- **THEN** the pending save is cancelled, no request is sent, and no exception is raised

#### Scenario: A save whose fields have gone is abandoned, not guessed

- **WHEN** a save runs while the control backing one of its fields is absent from the DOM
- **THEN** no request is sent, and no value is written for that field

#### Scenario: A settled move still saves

- **WHEN** a creator moves the map and leaves the panel open past the debounce
- **THEN** the position is saved and the indicator reports success, unchanged from the current behaviour

#### Scenario: Teardown and guard are independently verified

- **WHEN** the teardown hook is absent but the fields are unreadable
- **THEN** the save is still abandoned without raising, so a missed teardown degrades to a skipped save rather than an exception
