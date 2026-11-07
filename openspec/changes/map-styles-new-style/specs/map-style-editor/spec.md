## MODIFIED Requirements

### Requirement: Contrast warnings are advice, not a gate
The editor SHALL compute the greyscale luminance difference between parks, water, road casing, major and minor labels and the land colour and SHALL show a warning under a control whose difference is below 0.08; warnings SHALL NOT block saving.

#### Scenario: Pale parks on white
- **WHEN** land is `#ffffff` and parks `#f4f9f0`
- **THEN** the parks control shows the photocopy warning and Save still works

#### Scenario: Paper A's parks do not warn
- **WHEN** land is `#ffffff` and parks `#dcefd2`
- **THEN** no warning shows under parks
