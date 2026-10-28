## ADDED Requirements

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
