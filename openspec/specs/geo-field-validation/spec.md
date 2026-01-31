## ADDED Requirements

### Requirement: Geo fields use data-required attribute

The system SHALL use `data-required="true"` attribute instead of HTML5 `required` attribute on hidden geo-input fields to mark required geographic questions.

#### Scenario: Required geo-question renders with data-required
- **WHEN** a geo-question (point, line, or polygon) is marked as required in the admin
- **THEN** the hidden input element SHALL have `data-required="true"` attribute
- **AND** the hidden input element SHALL NOT have the `required` attribute

### Requirement: Client-side validation for required geo fields

The system SHALL validate that all geo-input fields marked with `data-required="true"` have a value before allowing form submission.

#### Scenario: Form submission blocked when required geo field is empty
- **WHEN** user clicks the submit/next button
- **AND** a geo-input field has `data-required="true"`
- **AND** the geo-input field value is empty
- **THEN** the form submission SHALL be prevented
- **AND** an error message SHALL be displayed to the user

#### Scenario: Form submission allowed when required geo field has value
- **WHEN** user clicks the submit/next button
- **AND** all geo-input fields with `data-required="true"` have non-empty values
- **THEN** the form submission SHALL proceed normally

### Requirement: Visual feedback for validation errors

The system SHALL provide visual feedback when a required geo field fails validation.

#### Scenario: Draw button highlighted on validation error
- **WHEN** validation fails for a required geo field
- **THEN** the corresponding draw button SHALL be visually highlighted (red border)
- **AND** the page SHALL scroll to the first invalid field

#### Scenario: Error message displayed
- **WHEN** validation fails for a required geo field
- **THEN** an alert or notification SHALL display indicating which field requires input
