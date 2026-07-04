## ADDED Requirements

### Requirement: Made-with-Mapsurvey CTA on public survey pages
The public survey-answering page and the thanks page SHALL show a "Made with Mapsurvey" call-to-action
that links to registration, when the survey's `show_branding` setting is on. The CTA SHALL be visually
minimal so it does not erode respondent trust in the survey.

#### Scenario: CTA on the thanks page
- **WHEN** a respondent reaches the thanks page of a survey with `show_branding` on
- **THEN** a "Made with Mapsurvey" CTA linking to registration is shown

#### Scenario: CTA on the survey-answering page
- **WHEN** a respondent views a section of a survey with `show_branding` on
- **THEN** a "Made with Mapsurvey" CTA linking to registration is shown

### Requirement: CTA is UTM-tagged for attribution
The CTA link SHALL carry `utm_source=viral_loop` and a `utm_medium` identifying the page it came from
(e.g. `survey`, `thanks`), so a resulting registration is attributed to the viral loop via signup
attribution.

#### Scenario: UTM parameters present
- **WHEN** the CTA is rendered on the thanks page
- **THEN** its link includes `utm_source=viral_loop` and `utm_medium=thanks`

#### Scenario: Medium identifies the survey page
- **WHEN** the CTA is rendered on the survey-answering page
- **THEN** its link includes `utm_medium=survey`

### Requirement: Creator toggle for branding
A survey SHALL have a `show_branding` setting, defaulting to on, that the creator can turn off to hide
the CTA (for a clean, unbranded look). When off, no CTA SHALL appear on that survey's public pages.

#### Scenario: Default on
- **WHEN** a survey is created without specifying the setting
- **THEN** `show_branding` is on

#### Scenario: Toggled off hides the CTA
- **WHEN** a creator turns `show_branding` off
- **THEN** the survey and thanks pages show no "Made with Mapsurvey" CTA

### Requirement: Setting persists across serialization and versioning
The `show_branding` setting SHALL be included in survey export/import and SHALL be preserved when a
survey is cloned for a draft and when a draft is published.

#### Scenario: Round-trips through serialization
- **WHEN** a survey is serialized
- **THEN** the exported data includes `show_branding`, and importing it restores the value (default on when absent)

#### Scenario: Preserved through versioning
- **WHEN** a survey is cloned to a draft or the draft is published
- **THEN** the `show_branding` value carries over
