## ADDED Requirements

### Requirement: Map pane empty state names the actual gap
When the Responses Map pane has no features to draw, it SHALL distinguish a survey with no
point/line/polygon questions ("No geo questions in this survey", with an action to add one)
from a survey whose geo questions have no answers yet ("No map answers yet", with no editor
action). The distinction SHALL hold on both the v2 and the legacy dashboard.

#### Scenario: Geo question without answers
- **WHEN** the survey has a point question and no answers
- **THEN** the Map pane says "No map answers yet" and does not claim there are no geo questions

#### Scenario: No geo question
- **WHEN** the survey has only non-geo questions
- **THEN** the Map pane says "No geo questions in this survey" and offers "Add a map question"
