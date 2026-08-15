# Survey Editor — Delta

## ADDED Requirements

### Requirement: Rating display style picker
The question modal SHALL include a "Display as" control offering three options — "Survey default" (`default`), "Compact scale" (`scale_strip`), "Labeled list" (`list_pips`) — the two visual styles with a small preview thumbnail each. The control SHALL be visible only while the selected input type is `rating`, and its value SHALL persist to `Question.display_style` on save.

#### Scenario: Picker appears for rating questions
- **WHEN** the user opens the question modal and selects input_type `rating`
- **THEN** the "Display as" control becomes visible with "Survey default" preselected for a new question

#### Scenario: Picker hidden for other types
- **WHEN** the user switches the modal's input_type from `rating` to `choice`
- **THEN** the "Display as" control is hidden and does not affect the saved question

#### Scenario: Choosing a style persists
- **WHEN** the user selects "Labeled list" and saves the question
- **THEN** the question's `display_style` is `list_pips` and only this question is modified

### Requirement: Modal preview reflects display style
The question modal's preview iframe SHALL render the rating question with the same markup as the respondent view, using the question's resolved display style. When the user switches the "Display as" picker, the preview SHALL update to the newly picked style immediately, without saving.

#### Scenario: Preview uses the new renderers
- **WHEN** the modal preview renders a rating question resolved to `scale_strip`
- **THEN** the preview shows the numbered scale strip, not the legacy pill buttons

#### Scenario: Preview follows the picker before saving
- **WHEN** the user switches the picker from "Compact scale" to "Labeled list" without saving
- **THEN** the preview re-renders as a labeled list

### Requirement: Survey style settings
The survey settings page SHALL include a "Style" section with the survey-wide default rating display style ("Compact scale" / "Labeled list"). Saving SHALL persist the value to `SurveyHeader.style_settings.rating_display_style`.

#### Scenario: Default style saved
- **WHEN** the user selects "Labeled list" in the settings Style section and saves
- **THEN** `style_settings.rating_display_style` is `list_pips` and rating questions with `display_style = "default"` render as labeled lists

#### Scenario: Settings page without explicit choice keeps prior behavior
- **WHEN** a survey has never configured the Style section
- **THEN** its effective default rating style is `scale_strip`
