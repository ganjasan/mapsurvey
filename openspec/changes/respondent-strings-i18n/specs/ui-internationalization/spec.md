## ADDED Requirements

### Requirement: Respondent interface strings are translated in every catalog
Every interface msgid that a respondent page looks up through gettext SHALL have a non-empty,
non-fuzzy translation in every catalog under `survey/locale/`. Respondent pages are the language
choice, every section page, the thanks page and the report form, rendered for an anonymous
visitor. Strings shown only to a signed-in creator are not respondent strings. A test SHALL render
these pages for a survey that uses every question type and display feature, record the msgids
looked up, and fail when one of them lacks a translation in any catalog.

#### Scenario: New respondent string without translations
- **WHEN** a template rendered on a section page gains `{% trans "Show all options" %}` and no catalog translates it
- **THEN** the respondent catalog test fails and names the msgid and the languages missing it

#### Scenario: Fuzzy guess is not a translation
- **WHEN** `makemessages` leaves `Tap the map to mark a place — or use the button.` as a `#, fuzzy` entry in the German catalog
- **THEN** the respondent catalog test fails for `de`, because gettext ignores fuzzy entries at runtime

#### Scenario: Portuguese survey shows Portuguese chrome
- **WHEN** a respondent opens a section of a survey in Portuguese that uses the icon grid and tap-to-place
- **THEN** the "show all options" control, the tap hint, the safety footer and the report link are in Portuguese

#### Scenario: Creator chrome is out of scope
- **WHEN** `base.html` renders the account menu (`Plan & billing`, `Pro help`) for a signed-in creator
- **THEN** those msgids are not required by the respondent catalog test, which renders as an anonymous visitor
