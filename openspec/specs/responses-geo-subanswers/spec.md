# responses-geo-subanswers Specification

## Purpose

Visibility of geo sub-question answers (mapped-object attributes) in the editor Responses
screen: the analytics geo feature payload carries each object's sub-answers, the map shows
them in a click popup, and the session detail modal lists them per object. Until this
capability existed, the only way to see collected attributes was the ZIP export.
## Requirements
### Requirement: Geo feature payloads carry sub-answer attributes
The Responses analytics geo feature collection SHALL include, for every geo answer feature, an ordered `attributes` list of `{name, value}` pairs built from the answers attached to that geo answer via `parent_answer_id`, ordered by sub-question `order_number`. Display values SHALL be formatted per input type (choice/multichoice/rating → selected choice names, number/range → numeric value, text/text_line/datetime → text). Unanswered sub-questions and sub-questions of non-displayable types (geo, image, html) SHALL be omitted. Existing feature properties (`question`, `type`, `session_id`) SHALL be preserved unchanged. Sub-answers SHALL be fetched with a bounded number of queries independent of the number of features.

#### Scenario: Point with answered sub-questions
- **WHEN** the geo feature collection is built for a survey where a point answer has sub-answers for a choice sub-question and a number sub-question
- **THEN** that feature's `properties.attributes` contains both pairs in sub-question order, with the choice rendered as its selected choice name(s) and the number as its numeric value

#### Scenario: Object with no sub-answers
- **WHEN** a geo answer has no child answers
- **THEN** its feature has an empty `attributes` list and its other properties are unchanged

#### Scenario: Free-text sub-answer is visible to the creator
- **WHEN** a sub-answer of type `text` or `text_line` exists on a geo answer
- **THEN** its text appears in `attributes` (the public-results text exclusion does not apply to the editor)

### Requirement: Responses map popup shows object attributes

On the Responses map, a pointer-mode click on a geo feature SHALL open a popup at the feature
showing the question name and the feature's attribute rows, without changing the existing selection
behavior of the click. Details-mode click behavior (opening the session modal) SHALL be unchanged.
Popup content SHALL be inserted as text (never markup built from answer values), with one
exception: a file sub-answer renders as a link whose href is a signed URL minted by the server and
whose visible text is the file's original name inserted as text.

#### Scenario: Pointer-mode click opens popup and selects

- **WHEN** the creator clicks a point feature with attributes in pointer mode
- **THEN** the session is selected as before AND a popup opens listing each attribute as
  "name: value"

#### Scenario: Attribute value containing markup is inert

- **WHEN** a sub-answer value contains `<script>` or other HTML
- **THEN** the popup renders it as literal text and no markup is executed

#### Scenario: A file sub-answer is a signed link, not a value-built URL

- **WHEN** the clicked feature carries a photo sub-answer
- **THEN** the popup shows the file's original name linking to a server-minted signed URL
- **AND** no part of the href is assembled from respondent-controlled text

#### Scenario: A filename containing markup is inert

- **WHEN** an uploaded file's original name contains `<img onerror=…>` or other HTML
- **THEN** the popup renders the name as literal text and no markup is executed

### Requirement: Session detail modal lists sub-answers per geo object
Each geo object is its own Answer row in the session detail modal. The modal SHALL show, under each geo answer row, that object's sub-answer name/value pairs. When a session contains several objects for the same geo question, the rows' values SHALL be numbered ("point feature 1", "point feature 2") so their attributes can be told apart; a single object keeps the un-numbered value. Object ordering SHALL be deterministic (creation order). Sub-answer values SHALL be rendered through template autoescaping, and any JSON payload embedding feature properties SHALL NOT be marked safe.

#### Scenario: Session with two points for one geo question
- **WHEN** the modal opens for a session whose geo question has two point answers with different sub-answers
- **THEN** the two geo rows are numbered and each shows its own object's attribute list

#### Scenario: Geo answer without sub-answers
- **WHEN** a geo answer in the session has no child answers
- **THEN** its row renders as today, with no empty attribute group

