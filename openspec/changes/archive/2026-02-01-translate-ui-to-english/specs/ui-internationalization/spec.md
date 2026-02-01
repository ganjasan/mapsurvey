## ADDED Requirements

### Requirement: All user-facing strings use Django i18n
The system SHALL wrap all user-facing text strings with Django i18n functions (`{% trans %}`, `{% blocktrans %}`, or `gettext`).

#### Scenario: Template string translation
- **WHEN** a template contains user-facing text
- **THEN** the text MUST be wrapped with `{% trans "text" %}` or `{% blocktrans %}` tags

#### Scenario: Navigation buttons are translatable
- **WHEN** user views survey navigation (Back, Next, Finish, Start buttons)
- **THEN** button labels MUST be rendered from translation catalogs

### Requirement: JavaScript receives translated strings
The system SHALL provide translated strings to JavaScript code via a JSON object in the page's data attributes.

#### Scenario: i18n JSON available in DOM
- **WHEN** a page with JavaScript translations loads
- **THEN** `document.body.dataset.i18n` MUST contain a valid JSON object with translated strings

#### Scenario: Leaflet.draw tooltips are translated
- **WHEN** user interacts with map drawing tools
- **THEN** all tooltips (marker placement, polygon drawing, line drawing) MUST display in the current language

### Requirement: English is the default language
The system SHALL use English (`en-us`) as the default language.

#### Scenario: Default language setting
- **WHEN** the application starts without language preference
- **THEN** `LANGUAGE_CODE` in settings MUST be `en-us`

#### Scenario: New users see English interface
- **WHEN** a new user visits the survey without language cookies
- **THEN** all interface text MUST be displayed in English

### Requirement: Russian translation is available
The system SHALL maintain Russian translation files for backward compatibility.

#### Scenario: Russian locale files exist
- **WHEN** the locale directory is checked
- **THEN** `survey/locale/ru/LC_MESSAGES/django.po` MUST exist with all translated strings

### Requirement: Translation catalog structure
The system SHALL organize translation files in Django's standard locale directory structure.

#### Scenario: Locale directory structure
- **WHEN** translations are configured
- **THEN** files MUST be located at `survey/locale/{lang}/LC_MESSAGES/django.po`

#### Scenario: LOCALE_PATHS configured
- **WHEN** Django loads translation catalogs
- **THEN** `LOCALE_PATHS` in settings MUST include the survey app's locale directory

### Requirement: Email templates are translatable
The system SHALL wrap email template content with i18n tags.

#### Scenario: Activation email subject is translatable
- **WHEN** activation email is sent
- **THEN** subject line MUST be rendered from translation catalog

#### Scenario: Activation email body is translatable
- **WHEN** activation email is sent
- **THEN** email body text MUST be rendered from translation catalog

### Requirement: Registration templates are translatable
The system SHALL wrap all registration flow text with i18n tags.

#### Scenario: Registration complete page
- **WHEN** user completes registration
- **THEN** all text on confirmation page MUST be rendered from translation catalog

#### Scenario: Activation pages
- **WHEN** user views activation success or failure page
- **THEN** all text MUST be rendered from translation catalog
