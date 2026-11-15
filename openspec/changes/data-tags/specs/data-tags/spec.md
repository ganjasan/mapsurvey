## ADDED Requirements

### Requirement: Datasets and surveys carry workspace tags
The system SHALL let an editor give a dataset or a survey free tags of the workspace, created on first
use and matched by their slug, at most 10 per item, and SHALL delete a tag nothing carries any more.

#### Scenario: Tagging a dataset and a survey alike
- **WHEN** an editor tags a dataset "Riverside plan 2027" and a survey "riverside plan 2027"
- **THEN** the workspace has one tag carried by both

#### Scenario: A tag nothing carries
- **WHEN** the only item carrying a tag drops it
- **THEN** the tag is gone

### Requirement: Lists filter by tag
The system SHALL filter the Data catalogue and the survey dashboard by a tag and SHALL show each item's
tags on its row or card.

#### Scenario: The catalogue filter
- **WHEN** a member opens the catalogue filtered by "riverside-plan-2027"
- **THEN** only the datasets carrying that tag are listed

#### Scenario: The dashboard filter
- **WHEN** a member opens the dashboard filtered by the tag
- **THEN** only the surveys carrying it are listed

### Requirement: Tags ride the API and MCP
The system SHALL return a survey's tags in the REST API and MCP, SHALL filter the survey list by tag,
and SHALL let a client with the editor role replace a survey's tags.

#### Scenario: Setting tags over the API
- **WHEN** a client puts the tags ["Riverside plan 2027"] on a survey
- **THEN** the survey's API representation lists that tag and the list filtered by it returns the survey

#### Scenario: Setting tags over MCP
- **WHEN** an agent calls set_survey_tags with ["Parks"]
- **THEN** list_surveys with tag "parks" returns the survey
