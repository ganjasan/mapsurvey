### Requirement: Survey section page displays progress indicator

The survey section page SHALL display a progress indicator showing the current section number and the total number of sections in the survey (e.g., "3 / 7").

#### Scenario: Progress indicator on first section

- **WHEN** the user opens the first section of a 5-section survey
- **THEN** the page displays "1 / 5" in the header area

#### Scenario: Progress indicator on middle section

- **WHEN** the user navigates to the 3rd section of a 7-section survey
- **THEN** the page displays "3 / 7" in the header area

#### Scenario: Progress indicator on last section

- **WHEN** the user navigates to the last section of a 4-section survey
- **THEN** the page displays "4 / 4" in the header area

### Requirement: Progress indicator is computed from section linked list

The view SHALL compute the current section index and total section count by traversing the `prev_section` / `next_section` linked list on `SurveySection`. No new model fields are required.

#### Scenario: Section position derived from linked list

- **WHEN** sections A → B → C → D are linked via `next_section`
- **AND** the user is on section C
- **THEN** `section_current` is 3 and `section_total` is 4

### Requirement: Progress values available in template context

The `survey_section` view SHALL pass `section_current` (integer, 1-based) and `section_total` (integer) in the template context.

#### Scenario: Template context contains progress values

- **WHEN** the survey section view renders
- **THEN** the template context includes `section_current` and `section_total` as integers
