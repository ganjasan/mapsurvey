## ADDED Requirements

### Requirement: Plausible script is configurable via environment variable
The system SHALL read `PLAUSIBLE_SCRIPT_URL` from an environment variable. It defaults to empty string (analytics disabled). The value SHALL be exposed to all templates via an `analytics` context processor.

#### Scenario: Environment variable is set
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is set to a Plausible script URL (e.g., `https://plausible.io/js/pa-lwntAkTnmyk5UaA7Vjaw4.js`)
- **THEN** the context processor SHALL inject `PLAUSIBLE_SCRIPT_URL` into every template context

#### Scenario: Environment variable is not set
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is not set in the environment
- **THEN** the context processor SHALL inject `PLAUSIBLE_SCRIPT_URL=''` (empty string) into every template context

### Requirement: Plausible script tag renders on all pages when configured
The system SHALL render the Plausible `<script async src="..."></script>` tag and init block in the `<head>` of every page when `PLAUSIBLE_SCRIPT_URL` is non-empty. The script SHALL be included via a shared template partial (`partials/_analytics.html`) in all 4 base templates: `base_survey_template.html`, `base.html`, `base_landing.html`, `editor/editor_base.html`.

#### Scenario: Analytics enabled
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is set
- **THEN** every page SHALL contain the async script tag and `plausible.init()` block in the HTML head

#### Scenario: Analytics disabled
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is empty or unset
- **THEN** no Plausible script tag SHALL appear in any page's HTML

### Requirement: Yandex Metrica is removed
The hardcoded Yandex Metrica script (counter ID 53686546) SHALL be removed from `base_survey_template.html`. No Yandex Metrica code SHALL remain in any template.

#### Scenario: Yandex Metrica absent
- **WHEN** any page is rendered
- **THEN** the HTML SHALL NOT contain any reference to `mc.yandex.ru` or Yandex Metrica counter code

### Requirement: Survey start event fires on first section
The system SHALL fire a `survey_start` Plausible custom event when a respondent views the first section of a survey. The event SHALL include a `survey` property with the survey name.

#### Scenario: First section loaded
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is configured AND the respondent loads the first section of a survey (no previous section exists)
- **THEN** the page SHALL call `plausible('survey_start', {props: {survey: '<survey_name>'}})` on page load

#### Scenario: Non-first section loaded
- **WHEN** the respondent navigates to a section that is not the first section
- **THEN** the `survey_start` event SHALL NOT fire

### Requirement: Survey section complete event fires on form submit
The system SHALL fire a `survey_section_complete` Plausible custom event when a respondent submits a section form. The event SHALL include `survey`, `section`, and `section_number` properties.

#### Scenario: Section form submitted
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is configured AND the respondent submits a section form
- **THEN** the page SHALL call `plausible('survey_section_complete', {props: {survey: '<name>', section: '<section_name>', section_number: <N>}})` before the form navigates away

### Requirement: Survey complete event fires on thanks page
The system SHALL fire a `survey_complete` Plausible custom event when the thanks page loads. The event SHALL include a `survey` property with the survey name.

#### Scenario: Thanks page loaded
- **WHEN** `PLAUSIBLE_SCRIPT_URL` is configured AND the respondent reaches the thanks page
- **THEN** the page SHALL call `plausible('survey_complete', {props: {survey: '<survey_name>'}})` on page load

### Requirement: Events are guarded against blocked scripts
All custom event calls SHALL be guarded with `typeof plausible !== 'undefined'` to gracefully handle cases where the Plausible script is blocked by ad-blockers.

#### Scenario: Plausible script blocked by ad-blocker
- **WHEN** the Plausible script fails to load (e.g., blocked by browser extension)
- **THEN** the event scripts SHALL NOT throw JavaScript errors
