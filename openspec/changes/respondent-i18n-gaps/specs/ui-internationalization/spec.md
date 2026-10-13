## ADDED Requirements

### Requirement: Respondent strings are translated in every survey locale
The system SHALL ship a non-empty, non-fuzzy translation for every respondent-facing msgid in every
non-English catalog under `survey/locale/` that the editor's language picker offers as a survey
language. Respondent-facing msgids are those referenced from the survey-taking pages, the thanks,
password, closed, unavailable and abuse-report pages, public results, and the strings the
`i18n_json` tag hands to respondent JavaScript.

#### Scenario: A new respondent string without translations fails the suite
- **WHEN** a respondent template gains `{% trans "New label" %}` and the catalogs are not updated
- **THEN** the catalog-completeness test MUST fail and name the msgid and the locales missing it

#### Scenario: A fuzzy guess does not count as a translation
- **WHEN** `makemessages` marks a respondent entry `#, fuzzy`
- **THEN** the catalog-completeness test MUST treat that entry as untranslated

#### Scenario: "Other" write-in placeholder follows the survey language
- **WHEN** a respondent of a Polish survey selects an "Other" choice
- **THEN** the write-in field placeholder MUST read the Polish translation of "Please specify"

#### Scenario: Right-to-left catalogs are not empty
- **WHEN** a survey is published in Arabic, Persian, Hebrew or Urdu
- **THEN** its navigation buttons and map hints MUST render from that language's catalog

### Requirement: Map controls and client-side messages are translatable
The system SHALL render every respondent-visible text produced by Leaflet controls and respondent
JavaScript from translation catalogs, including control titles and screen-reader announcements.

#### Scenario: Map control titles
- **WHEN** a respondent of a German survey hovers the zoom, locate or layers control
- **THEN** the title and aria-label MUST be the German translation

#### Scenario: Basemap names
- **WHEN** a survey offers more than one basemap
- **THEN** the basemap names in the layers control MUST be translated

#### Scenario: Ranking announcements
- **WHEN** a respondent reorders a ranking item with the keyboard
- **THEN** the live-region announcement MUST be in the survey language

#### Scenario: File upload errors
- **WHEN** a file upload fails, is too large, or a required file is missing
- **THEN** the error text MUST be in the survey language

#### Scenario: Thanks-page share button
- **WHEN** a respondent of a survey in any supported language reaches the thanks page
- **THEN** the share button and its "copied" confirmation MUST be in that language
