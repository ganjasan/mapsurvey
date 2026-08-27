## MODIFIED Requirements

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
