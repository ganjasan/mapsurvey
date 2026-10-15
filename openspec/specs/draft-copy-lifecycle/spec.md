# draft-copy-lifecycle Specification

## Purpose
TBD - created by archiving change draft-results-scope. Update Purpose after archive.
## Requirements
### Requirement: Discarding a draft copy succeeds regardless of test sessions

Discarding a draft copy SHALL delete the draft's own test sessions together with the draft header,
in one transaction, and SHALL then redirect to the canonical survey. A draft that has been previewed
SHALL be discardable.

#### Scenario: A previewed draft is discarded

- **WHEN** a draft copy that has test sessions is discarded
- **THEN** the draft, its sections and its test sessions are gone
- **AND** the creator is redirected to the canonical survey

#### Scenario: The canonical survey is untouched

- **WHEN** a draft copy with test sessions is discarded
- **THEN** the canonical survey's sessions, sections and version number are unchanged

#### Scenario: Discard is atomic

- **WHEN** deleting the draft header fails
- **THEN** its test sessions are not deleted either

### Requirement: Publishing a draft never fails silently

The publish-draft flow SHALL give the creator visible feedback for every outcome of its
requests. When the compatibility-check request or the publish request cannot complete —
network failure, blocked request, or a non-OK response whose body is not the expected JSON —
the creator MUST see an error message; the button MUST NOT silently do nothing.

#### Scenario: Compatibility check request fails at network level

- **WHEN** the creator clicks "Publish draft" and the compatibility-check request is blocked
  or the network is down
- **THEN** a visible message tells the creator the server could not be reached and suggests
  checking the connection and any ad blocker

#### Scenario: Compatibility check returns a non-OK response

- **WHEN** the compatibility-check endpoint answers with an error status (e.g. a 500 page)
- **THEN** the same visible failure message is shown and no attempt is made to parse the
  body as JSON

#### Scenario: Publish request fails at network level

- **WHEN** the creator confirms publishing and the publish POST is blocked or the network
  is down
- **THEN** the same visible failure message is shown

#### Scenario: Existing HTTP-status error handling is preserved

- **WHEN** the publish POST answers with an error status (409 translation gaps, 409
  compatibility, other errors)
- **THEN** the existing status-specific messages are shown unchanged


### Requirement: A draft copy is structurally complete

Creating a draft copy of a published survey SHALL copy every field of every section, question and
translation that describes the questionnaire — including the section `layout`, `next_label`,
`hidden_layers` and `visibility_rule`, the translations' `next_label`, and the questions'
`visibility_rule` — so that publishing an untouched draft leaves the live survey structurally
identical. Section and question copies SHALL take their plain fields from the model's field list,
not from a hand-written list, so a field added later is copied without a code change.

#### Scenario: Untouched draft publishes identically

- **GIVEN** a live survey with a conditional question, a conditional section, a form-layout section
  with a custom forward label and a translated label, and a section that hides a reference layer
- **WHEN** the creator starts unpublished changes and publishes them without editing anything
- **THEN** the live survey still has the two rules, the form layout, both labels and the hidden layer

#### Scenario: Every concrete field survives the copy

- **WHEN** a draft copy is created
- **THEN** every concrete non-relational field of each section, section translation, question and
  question translation equals the live row's value

#### Scenario: Restoring an archived version keeps its rules and layout

- **WHEN** an archived version is restored as a new draft
- **THEN** the draft carries that version's rules, layouts and labels
