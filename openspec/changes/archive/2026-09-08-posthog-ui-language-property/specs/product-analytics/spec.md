## ADDED Requirements

### Requirement: Identified creators carry their interface language
The system SHALL set the PostHog person property `ui_language` to the creator's stored interface
language (`CreatorPreferences.ui_language`, empty string when the creator follows the browser)
whenever the preference is saved, and the person-properties sync command SHALL set the same
property for every existing creator. Setting the property SHALL be fail-open and SHALL never alter
the language switch itself.

#### Scenario: Switching the interface language updates the person
- **WHEN** a signed-in creator switches the editor language to German
- **THEN** a person-property update with `ui_language='de'` is sent for that creator and the
  switch completes as before

#### Scenario: Sync backfills the property
- **WHEN** `sync_posthog_person_properties` runs
- **THEN** every creator's property set includes `ui_language`, `''` for creators without a
  stored preference

#### Scenario: PostHog unavailable
- **WHEN** PostHog is disabled or the update raises
- **THEN** the language switch succeeds and nothing is sent
