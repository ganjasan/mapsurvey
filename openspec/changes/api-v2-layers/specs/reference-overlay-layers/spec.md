## ADDED Requirements

### Requirement: Object links are web links only
A layer object's `link` SHALL be empty or an absolute `http`/`https` URL of at most 500 characters on
every write path — the object editor, the API, GeoJSON and CSV imports and ZIP import. The object
editor and the API SHALL refuse another value naming the field; imports SHALL drop it and count it in
their report. The respondent's object card SHALL render a link only when it is `http`/`https`, so a
value stored before this rule never becomes a clickable `href`.

#### Scenario: Script link in the editor
- **WHEN** the owner saves an object with link `javascript:alert(document.cookie)`
- **THEN** the save is refused with a message about the link and the stored link is unchanged

#### Scenario: Old bad link on the card
- **WHEN** an object stored before the rule has link `javascript:alert(1)` and a respondent opens its card
- **THEN** the card payload has no link and no `href` is rendered

#### Scenario: Import drops a bad link
- **WHEN** a CSV import row has link `data:text/html,<script>`
- **THEN** the object is imported without a link and the report counts one invalid link
