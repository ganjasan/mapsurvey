# UI Internationalization (Delta)

This delta spec extends the existing ui-internationalization capability to support automatic language switching based on survey language selection.

## ADDED Requirements

### Requirement: UI language switches based on survey language selection
The system SHALL automatically activate the Django i18n language matching the respondent's survey language selection.

#### Scenario: Language activation on selection
- **WHEN** a respondent selects a language on the language selection screen
- **THEN** the Django translation system MUST be activated with that language code

#### Scenario: Language persists in session
- **WHEN** a respondent has selected a survey language
- **THEN** the Django session MUST store the language preference for subsequent requests

#### Scenario: UI elements in selected language
- **WHEN** a respondent is viewing a survey after language selection
- **THEN** all UI elements (buttons, navigation, tooltips) MUST be displayed in the selected language

### Requirement: Language selection screen is displayed in browser language
The system SHALL display the language selection screen in the browser's preferred language (if available) or default language.

#### Scenario: Browser language detection
- **WHEN** the language selection screen is loaded
- **THEN** the system MUST attempt to display UI text in the browser's Accept-Language preference

#### Scenario: Fallback to default language
- **WHEN** the browser's preferred language is not available
- **THEN** the system MUST display UI text in the default language (English)
