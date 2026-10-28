# survey-editor (delta)

## ADDED Requirements

### Requirement: Editor layout adapts below 768px
On viewports narrower than 768px the survey editor SHALL NOT rely on the three-pane
side-by-side layout: exactly one pane is presented at a time (see
`editor-mobile-navigation`), the page SHALL have no horizontal overflow, and all
interactive controls SHALL meet a 44px minimum touch target. The desktop three-pane layout
SHALL remain unchanged at 768px and above.

#### Scenario: No horizontal overflow on mobile
- **WHEN** the editor is opened at 390px width with the mobile navigation flag enabled
- **THEN** the document's scroll width does not exceed the viewport width

#### Scenario: Read-only banner fits mobile
- **WHEN** a published (read-only) survey version is opened at 390px width
- **THEN** the read-only banner renders without overlapping its own text and its action button is fully visible
