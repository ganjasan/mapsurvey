## ADDED Requirements

### Requirement: Settings panel saves the language picker
The Survey settings panel autosave SHALL save `available_languages` whenever the creator adds or
removes a language in the language picker, with no other gesture. Typing in the picker's search box
SHALL NOT trigger a save. Opening the panel SHALL NOT trigger a save.

#### Scenario: A language added in the panel survives a reload
- **WHEN** the owner of an English survey picks "Spanish" in the settings panel's language picker and reopens the panel
- **THEN** SurveyHeader.available_languages is `["en", "es"]` and the picker shows both languages

#### Scenario: Filtering then picking saves the picked language
- **WHEN** the owner types "spa" in the picker's search box and clicks "Spanish"
- **THEN** the last settings POST carries `available_languages` containing `"es"`, and no POST is sent by the search box itself

#### Scenario: A removed language is saved
- **WHEN** the owner removes a language tag in the picker
- **THEN** SurveyHeader.available_languages no longer contains that language
