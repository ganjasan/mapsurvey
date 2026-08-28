## MODIFIED Requirements

### Requirement: All user-facing strings use Django i18n
The system SHALL wrap all user-facing text strings with Django i18n functions (`{% trans %}`, `{% blocktrans %}`, or `gettext`), across both respondent-facing and creator-facing surfaces.

#### Scenario: Template string translation
- **WHEN** a template contains user-facing text
- **THEN** the text MUST be wrapped with `{% trans "text" %}` or `{% blocktrans %}` tags

#### Scenario: Navigation buttons are translatable
- **WHEN** user views survey navigation (Back, Next, Finish, Start buttons)
- **THEN** button labels MUST be rendered from translation catalogs

#### Scenario: Editor templates are translatable
- **WHEN** a creator views any editor screen
- **THEN** its user-facing text MUST be rendered from translation catalogs rather than
  hardcoded English

#### Scenario: Account and authentication screens are translatable
- **WHEN** a creator views registration, login, activation or account screens
- **THEN** their user-facing text MUST be rendered from translation catalogs

#### Scenario: Editor-only labels are excluded
- **WHEN** a string is never shown to a person, such as a machine-readable value or a
  developer-facing debug string
- **THEN** it MUST NOT be wrapped, so catalogs stay limited to text a human reads

### Requirement: English is the default language
The system SHALL use English (`en`) as the default language.

#### Scenario: Default language setting
- **WHEN** the application starts without language preference
- **THEN** `LANGUAGE_CODE` in settings MUST be `en`

#### Scenario: New users see English interface
- **WHEN** a new user visits the survey without language cookies
- **THEN** all interface text MUST be displayed in English

### Requirement: Russian translation is available
The system SHALL maintain a Russian translation catalog whose entries are correct, in
addition to being present. A `msgstr` belonging to a different `msgid` is a defect, not an
incomplete translation.

#### Scenario: Russian locale files exist
- **WHEN** the locale directory is checked
- **THEN** `survey/locale/ru/LC_MESSAGES/django.po` MUST exist with all translated strings

#### Scenario: Russian entries match their source strings
- **WHEN** the Russian catalog is inspected
- **THEN** no `msgstr` MUST carry the translation of a different `msgid`, such as
  `Email address` rendering as «Поиск адреса...» or `Archived` as «Архитектура»

## ADDED Requirements

### Requirement: Respondent chrome language follows the survey
The system SHALL render respondent-facing interface strings in the language of the survey
being taken, independently of any viewer preference, browser header or stored setting.

#### Scenario: Survey language wins over viewer preference
- **WHEN** any viewer opens a survey whose language is German
- **THEN** the respondent chrome MUST render in German

#### Scenario: Respondent chrome coverage is preserved
- **WHEN** the locale catalogs are regenerated
- **THEN** the existing respondent-facing strings MUST remain translated in every locale
  where they were translated before

#### Scenario: Catalogs are merged, never recreated
- **WHEN** translation catalogs are regenerated
- **THEN** regeneration MUST merge into existing catalogs, and a catalog file MUST NOT be
  deleted and recreated, which would discard live respondent translations

### Requirement: Translation catalogs are free of reused translations
The system SHALL detect catalog entries where one `msgstr` is reused across semantically
different `msgid`s, which is the signature of a corrupted catalog.

#### Scenario: Reused translation is detected
- **WHEN** a catalog assigns the same `msgstr` to two `msgid`s that are not synonyms
- **THEN** the check MUST fail and name the offending entries

#### Scenario: Legitimate collisions are allowed
- **WHEN** two source strings legitimately share a translation, such as `Features` and
  `Capabilities` both rendering as «Возможности»
- **THEN** an explicit allow-list entry MUST permit that pair without weakening the check
