## ADDED Requirements

### Requirement: A rich-text hint renders once, inside its styled wrapper
Wherever a question's subtext or an image block's caption is shown to a respondent or in the editor's preview, the creator's rich text SHALL be placed inside a block-level wrapper, so that the browser keeps it inside the styled hint element. The hint SHALL appear exactly once and SHALL keep the hint style (smaller and muted relative to the question title).

#### Scenario: Geo question with a rich-text hint
- **WHEN** a respondent opens a section with a line question whose subtext is `<p>Subtest</p>`
- **THEN** the draw button shows "Subtest" once, in the muted subtitle style below the title

#### Scenario: Card question with a rich-text hint
- **WHEN** a respondent opens a section with a choice, text or rating question whose subtext is
  rich text
- **THEN** the hint renders inside the `question-card__subtext` element in the muted style

#### Scenario: Image block with a rich-text caption
- **WHEN** an image block has a rich-text caption
- **THEN** the caption renders inside the `image-block__caption` element
