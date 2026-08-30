# survey-editor — delta for fix-question-modal-error-retarget

## ADDED Requirements

### Requirement: Question modal validation errors are shown in the modal

When a question create, edit or sub-question create POST fails validation (form errors or
a Visibility-block error) and the modal is re-rendered, the response SHALL be swapped into
the modal body (`#questionModalBody`) and not into the form's success target (the
question list or a list item). The server SHALL express this with the HTMX
`HX-Retarget`/`HX-Reswap` response headers so no client script is required.

#### Scenario: Conditional mode without answers on create

- **WHEN** a creator submits the New question form with "Shown conditionally" selected
  and no answer of the controlling question ticked
- **THEN** the modal re-renders in place with the error "Pick a controlling question and
  at least one of its answers.", the question list is unchanged, and no question is
  created

#### Scenario: Invalid edit form

- **WHEN** an edit POST (non-autosave) fails validation
- **THEN** the modal re-renders in place and the question's list item is not replaced
  by the modal markup

### Requirement: Visibility block works in the question modal while the section panel is open

The Visibility block SHALL bind its picker behaviour per rendered instance, so that the
question modal's block works regardless of whether the section panel (which renders its
own block) is open on the same page. The block SHALL NOT rely on a page-unique element id.

#### Scenario: Picker unfolds in the modal next to an open section panel

- **WHEN** the section panel is open and the creator opens a question modal and selects
  "Shown conditionally"
- **THEN** the "When the answer to" select and the answer checkboxes of the modal's block
  become visible
