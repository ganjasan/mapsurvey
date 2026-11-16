## ADDED Requirements

### Requirement: Number Min and Max limit what a respondent can submit
A number question's `validation_settings.min_value` and `max_value`, when set, SHALL be rendered
as the `min` / `max` of the respondent's number input on the respondent, operator-entry and
paper-entry forms, so the browser refuses an out-of-range value before the page is submitted. A
submitted value outside the bounds SHALL NOT be stored. The question editor SHALL offer Min and
Max for number questions only; range questions take their bounds from their options.

#### Scenario: Browser refuses an out-of-range value
- **WHEN** a number question has Min 0 and Max 120 and the respondent types 150
- **THEN** the input carries `min="0" max="120"` and the page is not submitted

#### Scenario: Tampered POST
- **WHEN** a section POST carries 150 for that question
- **THEN** no answer is stored for it

#### Scenario: No bounds
- **WHEN** neither Min nor Max is set
- **THEN** the input has no `min` / `max` and any number is stored

#### Scenario: Editor offers bounds for number only
- **WHEN** the creator opens the question editor for a range question
- **THEN** no Min / Max fields are shown
