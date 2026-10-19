## ADDED Requirements

### Requirement: Optional colour on a choice object
A choice object SHALL accept an optional `color`. Every save path that normalises `icon` and `group` SHALL keep a `color` only when it is a string matching `#RRGGBB`, stored in lower case. Any other value SHALL be dropped. Every consumer other than the icon-grid rendering SHALL ignore it.

#### Scenario: Valid colour kept, normalised
- **WHEN** a choice is saved with `color = " #DC2626 "`
- **THEN** the stored entry carries `"color": "#dc2626"`

#### Scenario: Invalid colour dropped
- **WHEN** a choice is saved with `color = "red"` or `color = ""`
- **THEN** the stored entry has no `color` key
