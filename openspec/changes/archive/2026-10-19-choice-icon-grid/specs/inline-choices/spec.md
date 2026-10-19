## ADDED Requirements

### Requirement: Optional icon and group on a choice object
A choice object SHALL accept an optional `icon` and an optional `group`. The `icon` is a marker-icon value: a Font Awesome class or a `set:name` from the map sets. The `group` is plain text.

These save paths SHALL trim both keys: the editor's save, autosave, the live preview and ZIP import. They SHALL drop a key that is blank or not a string. They SHALL cap `group` at 60 characters and `icon` at 64. They SHALL keep every other key and the order of the choices.

Every consumer other than the icon-grid rendering SHALL ignore both keys. Answer storage, analytics, exports, public results and the list and dropdown renderings SHALL behave as if the keys were absent.

#### Scenario: Keys are stored when set
- **WHEN** the creator saves a choice with icon `maki:park` and group "Nature"
- **THEN** the stored entry is `{"code": 1, "name": "Park", "icon": "maki:park", "group": "Nature"}`

#### Scenario: Blank keys are not stored
- **WHEN** the creator saves choices with empty Icon and Group cells
- **THEN** the stored entries contain no `icon` or `group` key

#### Scenario: Export ignores the keys
- **WHEN** responses to a question whose choices carry icons are exported to CSV
- **THEN** the choice columns hold the option names exactly as before this change
