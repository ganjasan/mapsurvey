## ADDED Requirements

### Requirement: Sub-questions in a map popup render like section questions
The popup that opens on a placed feature and the object popup of an "Objects on the map" question SHALL render their sub-questions through the same per-question markup as the section form, so each sub-question shows its hint between its text and its input and keeps its display style.

#### Scenario: Hint in a feature popup
- **WHEN** a respondent places a point whose question has a sub-question with a hint
- **THEN** the popup shows the hint under the sub-question's text, in the hint style

#### Scenario: Rating style in a popup
- **WHEN** a rating sub-question uses the stars, labeled list or compact scale style
- **THEN** the popup renders that style, not bare radio buttons

#### Scenario: Answers survive the popup
- **WHEN** a respondent answers sub-questions, closes the popup and opens it again
- **THEN** the answers are restored and are saved with the feature on submit
