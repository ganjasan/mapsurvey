## ADDED Requirements

### Requirement: A view is a saved filter, field set and colour over a dataset
The system SHALL let an editor of a dataset create a named view of it with conditions on its public
fields, a set of public fields and a colour, SHALL keep its id across new versions of the dataset,
and SHALL refuse to delete a view something uses.

#### Scenario: Creating a view
- **WHEN** an editor creates the view "Poor condition" with the condition CONDITION is "poor" on a tree dataset
- **THEN** the dataset page lists the view

#### Scenario: A condition on a private field
- **WHEN** a view is posted with a condition on the private field INSP_EMAIL
- **THEN** the view is refused

#### Scenario: A view in use
- **WHEN** the owner deletes a view a survey shows
- **THEN** the view stays and the page says where it is used

### Requirement: A view is picked like a dataset
The system SHALL offer a layer dataset's views in the survey's "From Data" picker and in the Site map
block, and SHALL then serve only the objects that match the view, with only its fields, in its colour.

#### Scenario: The survey map shows the view
- **WHEN** a survey links the view "Poor condition"
- **THEN** the survey's layer GeoJSON holds only the trees in poor condition, without the fields the view leaves out

#### Scenario: The Site map block shows the view
- **WHEN** a Site map block shows the view
- **THEN** the block's GeoJSON holds only the matching trees

### Requirement: A view of aggregated data stays aggregated
The system SHALL make a view of an `aggregated` dataset a grid of counts of distinct respondents with
cells under K omitted, SHALL let it be shown in a Site map block only, and SHALL never return its
individual answers.

#### Scenario: A grid in a Site block
- **WHEN** a Site map block shows a view of a point question's answers from 5 respondents in one place and 1 elsewhere, with K = 3
- **THEN** the block's GeoJSON holds one cell with 5 respondents and no point

#### Scenario: Not a survey layer
- **WHEN** an owner links a view of answers into a survey
- **THEN** the link is refused
