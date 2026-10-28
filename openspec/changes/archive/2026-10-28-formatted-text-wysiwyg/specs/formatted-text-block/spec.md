## ADDED Requirements

### Requirement: The Formatted Text block is authored in a rich-text editor

The system SHALL present the Formatted Text block's body in a rich-text (WYSIWYG) editor
whenever `Formatted Text` (`input_type='html'`) is the selected type in the question dialog,
replacing the single-line Subtext input, and offering headings, bold/italic/underline, alignment, links,
ordered and bulleted lists, blockquote and clear-formatting. The body SHALL continue to be
stored in `Question.subtext`, which SHALL hold text of unbounded length.

#### Scenario: Selecting Formatted Text reveals the editor

- **WHEN** a creator selects `Formatted Text` in the question dialog
- **THEN** a rich-text editor is shown for the block's content and the plain Subtext input is not

#### Scenario: Other types keep the plain field

- **WHEN** any other input type is selected
- **THEN** the Subtext field is the ordinary single-line input

#### Scenario: Formatting is preserved through a save

- **WHEN** a creator writes a heading, a bold run and a bulleted list in the editor and saves
- **THEN** the stored `subtext` carries that markup and the respondent's page renders it formatted

#### Scenario: A body longer than 512 characters is accepted

- **WHEN** a creator saves a Formatted Text block whose body exceeds 512 characters
- **THEN** the block saves without a length error and renders in full

### Requirement: Formatted Text content is sanitized on save

Because the block is rendered `|safe` to respondents, the system SHALL sanitize a `html`
block's `subtext` — in the base language and in every translation — against a tag and
attribute allow-list before storing it, stripping scripts, event handlers and unknown
tags while keeping allow-listed formatting.

#### Scenario: A script is stripped

- **WHEN** a Formatted Text body containing `<script>` or an `onclick` attribute is saved
- **THEN** the stored `subtext` has it removed and keeps only allow-listed formatting

#### Scenario: Other input types are untouched

- **WHEN** a non-`html` question is saved with subtext containing angle brackets
- **THEN** the subtext is stored as typed, since it is escaped rather than rendered as markup

### Requirement: Each survey language has its own Formatted Text body

In a multilingual survey the system SHALL let the creator author the Formatted Text body per
available language in the same rich-text editor, stored in `QuestionTranslation.subtext`,
which SHALL hold text of unbounded length.

#### Scenario: Translating a Formatted Text block

- **WHEN** a survey has two languages and the creator edits a Formatted Text block
- **THEN** each language's body is edited in its own rich-text editor and saved to that language's translation

### Requirement: Question subtext and section subheading are rich text

The system SHALL let creators author a question's subtext and a section's subheading in a
rich-text editor offering emphasis, links and lists (plus alignment for the subheading), store
them as sanitized HTML of unbounded length, and render them as markup to respondents — in the
section page, the geo draw button, the image caption and the editor's preview alike.

#### Scenario: Formatted helper text reaches the respondent

- **WHEN** a creator writes a bolded word and a link in a question's subtext and saves
- **THEN** the respondent sees them rendered, not as tags

#### Scenario: A subheading is authored without HTML

- **WHEN** a creator edits a section's subheading
- **THEN** it is edited in the rich-text editor and saved by the panel's existing autosave

#### Scenario: Text that looks like a tag survives

- **WHEN** a creator types "takes <5 minutes" in a subtext
- **THEN** the respondent sees "takes <5 minutes"

#### Scenario: Text written before the editors existed still reads correctly

- **WHEN** a question saved earlier holds the plain subtext "takes <5 minutes"
- **THEN** it renders unchanged after this change, rather than losing the "<5 minutes"

#### Scenario: Machine-written text is not mistaken for markup

- **WHEN** an AI-generated draft or an older ZIP export supplies plain-text subtext containing `<` or `&`
- **THEN** it is escaped on import and renders as typed

### Requirement: The Name field is presented as an internal label for display blocks

The question dialog SHALL label the Name field as an internal one for `image` and `html` —
whose name is never rendered to respondents — so the creator does not mistake it for a
heading respondents will see.

#### Scenario: Name labelled on a display block

- **WHEN** `Formatted Text` or `Image` is the selected type
- **THEN** the Name field states that it identifies the block in the editor only
