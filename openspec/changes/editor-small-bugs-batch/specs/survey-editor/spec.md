# survey-editor — delta for editor-small-bugs-batch

## ADDED Requirements

### Requirement: Every disabled edit control on a live survey opens the new-version sheet
On a published or closed survey, clicking any disabled structural-edit control (New
Question in the section panel or sidebar, Add sub-question, Paste question, question
rows, section fields) SHALL open the "This survey is live and collecting responses"
sheet offering "Open a new version" — regardless of which wrapper element receives the
click.

#### Scenario: New Question in the section panel
- **WHEN** the creator clicks the disabled New Question button below the question list of a published survey
- **THEN** the live-survey sheet opens with "Open a new version"
