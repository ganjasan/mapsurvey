# UI Internationalization

## Purpose
This spec defines the internationalization (i18n) infrastructure for the survey application.
## Requirements
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

### Requirement: Localized numbers never reach inline JavaScript

Every template SHALL render server-side values into inline JavaScript with
localization disabled — `{% localize off %}` around the block, or `|unlocalize` on the
value. Human-readable readouts outside `<script>` SHALL stay localized.

Ten of the eleven shipped creator languages write decimals with a comma, so a float
rendered under an active locale becomes `50,9375`: such a `<script>` block either fails to
parse or parses the wrong value, and stops running entirely.

This SHALL be enforced by a repository-wide check over the template source, not by
asserting against a list of rendered URLs: the defect recurred in September 2026 because
a template added after the guard was written was outside the URLs the guard named.

#### Scenario: An unguarded coordinate in a new template fails the suite

- **WHEN** any template under `survey/templates/` interpolates a server-side value inside a `<script>` block that is not wrapped in `{% localize off %}` and not filtered through `|unlocalize`
- **THEN** the test suite fails and names that file and the offending interpolation

#### Scenario: The layer object editor initialises in a comma-decimal language

- **WHEN** a creator whose UI language is German opens `/editor/surveys/<uuid>/layers/<id>/edit/` for a survey positioned at 50.9375, 6.9603
- **THEN** the inline script contains `50.9375` and `6.9603` with decimal points, the Leaflet map initialises, and moving the pointer over it raises no exception

#### Scenario: Coordinates are identical in every language

- **WHEN** the same page is rendered under English and under German
- **THEN** the numbers inside its `<script>` blocks are byte-identical in both

#### Scenario: Readouts stay localized

- **WHEN** a German creator views the coordinates label beneath a map picker
- **THEN** the label renders in the creator's locale, because it is outside the script block

#### Scenario: The detector itself is pinned

- **WHEN** a template fragment of the shape this defect produced is rendered under a comma-decimal locale with no guard
- **THEN** the detector fires, proving it is capable of failing

