## ADDED Requirements

### Requirement: A creator's UI language is stored per user
The system SHALL persist each creator's chosen interface language against their user
account, so the choice survives a new session, a new browser, and a new device.

#### Scenario: Preference persists across sessions
- **WHEN** a creator selects Deutsch, logs out, and signs in again from another browser
- **THEN** the editor MUST render in German without the creator selecting it again

#### Scenario: No preference recorded yet
- **WHEN** a creator has never chosen a language
- **THEN** the stored preference MUST be empty and MUST NOT be treated as a choice of English

#### Scenario: Preference is not staff CRM data
- **WHEN** the language preference is stored
- **THEN** it MUST NOT be written to `CreatorProfile`, which holds staff-authored notes
  disclosed verbatim under a GDPR subject access request

### Requirement: Language resolution order for creator surfaces
The system SHALL determine the language of creator-facing pages by taking the first
available of: the stored preference, the `Accept-Language` header, then English.

#### Scenario: Stored preference wins over browser
- **WHEN** a creator's stored preference is Polish and their browser sends `Accept-Language: de`
- **THEN** the editor MUST render in Polish

#### Scenario: Browser language used when no preference
- **WHEN** a creator has no stored preference and their browser sends `Accept-Language: es`
- **THEN** the editor MUST render in Spanish

#### Scenario: English fallback
- **WHEN** a creator has no stored preference and sends no supported `Accept-Language`
- **THEN** the editor MUST render in English

#### Scenario: Unsupported language falls back
- **WHEN** a stored preference or header names a language outside the supported set
- **THEN** the system MUST fall back rather than error, and MUST NOT render partial translations

### Requirement: Creators can switch language from the interface
The system SHALL present a language switcher on creator-facing pages that changes the
interface language and updates the stored preference.

#### Scenario: Switching updates the page and the preference
- **WHEN** a creator selects Français in the switcher
- **THEN** the interface MUST render in French AND the stored preference MUST become French

#### Scenario: Switcher lists exactly the supported languages
- **WHEN** the switcher is displayed
- **THEN** it MUST list exactly English, Русский, Bahasa Indonesia, Deutsch, Español,
  Français, Português and Polski, each written in its own language

### Requirement: Creator language never overrides respondent language
The system SHALL render respondent-facing survey pages in the language of the survey,
regardless of any creator preference belonging to the signed-in user.

#### Scenario: Creator opens a survey in another language
- **WHEN** a creator whose preference is Polish opens a German survey at `/surveys/<uuid>/`
- **THEN** the respondent chrome MUST render in German

#### Scenario: Creator previews their own survey
- **WHEN** a creator whose preference is Polish previews a section of their German survey
- **THEN** the previewed respondent page MUST render in German

#### Scenario: No site-wide session language key is written
- **WHEN** a respondent selects a language on the survey language picker
- **THEN** the system MUST NOT write a site-wide Django language session key, which
  Django 4.2 does not read and which invites future cross-surface leakage

### Requirement: Supported creator interface languages
The system SHALL support exactly eight creator interface languages: English, Russian,
Indonesian, German, Spanish, French, Portuguese and Polish.

#### Scenario: LANGUAGES setting lists the supported set
- **WHEN** the Django `LANGUAGES` setting is read
- **THEN** it MUST contain exactly `en`, `ru`, `id`, `de`, `es`, `fr`, `pt`, `pl`

#### Scenario: Adding a language requires a catalog
- **WHEN** a language appears in `LANGUAGES`
- **THEN** a corresponding catalog MUST exist at `survey/locale/<lang>/LC_MESSAGES/django.po`
