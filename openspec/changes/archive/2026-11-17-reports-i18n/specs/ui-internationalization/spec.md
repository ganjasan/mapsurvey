## ADDED Requirements

### Requirement: Reports strings are translated in every offered language
The catalog of every language in `settings.LANGUAGES` other than English SHALL translate every string the Reports module shows through gettext: the Reports list and start page, the report editor and its dialogs, the public report page, the report PDF and the analysis-view preview in Data.

#### Scenario: A creator opens Reports in an offered language
- **WHEN** a creator whose interface language is one of the offered languages opens the Reports list, the
  start page or a report's editor
- **THEN** the strings of those screens are in that language

#### Scenario: A string is added to a Reports screen without a translation
- **WHEN** a literal string marked for translation is added to a Reports template or module and one offered
  catalog lacks it
- **THEN** the test suite fails and names the string and the language
