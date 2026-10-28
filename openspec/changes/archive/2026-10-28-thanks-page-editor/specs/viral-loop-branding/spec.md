## MODIFIED Requirements

### Requirement: Creator toggle for branding
The "Made with Mapsurvey" CTA SHALL be **mandatory** on a survey's public pages
(survey-answering, thanks, and results) for the free tier — it SHALL always be
shown and SHALL NOT be creator-removable. The `show_branding` field SHALL remain
on the model (default on) as a forward-looking preference reserved for a future
paid tier, but SHALL NOT be exposed as a creator-facing toggle now; turning it off
in data SHALL have no effect on the free tier's rendering.

#### Scenario: Branding always renders
- **WHEN** a respondent views any public page of any survey (survey/thanks/results)
- **THEN** the "Made with Mapsurvey" CTA is shown, whatever the value of `show_branding`

#### Scenario: No creator toggle
- **WHEN** a creator opens Survey settings or the thanks editor
- **THEN** there is no control to hide the branding

#### Scenario: Flag preserved for the future
- **WHEN** a survey is created, serialized, imported, cloned to a draft, or published
- **THEN** the `show_branding` field is retained (default on) so a future paid tier can honor it
