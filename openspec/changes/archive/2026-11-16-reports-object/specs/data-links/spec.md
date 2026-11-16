## MODIFIED Requirements

### Requirement: Every place that uses a dataset is listed
The system SHALL list on a dataset's page every place that uses it: the survey that owns it,
surveys and site blocks that link it, questions bound to it, and reports whose blocks read it.
Deleting a workspace dataset SHALL show that list before the delete is confirmed, SHALL be refused
while a question is bound to it, and SHALL remove its links otherwise.

#### Scenario: The delete page lists the places
- **WHEN** an editor opens the delete page of a dataset linked into a survey and a Site
- **THEN** the page names the survey and the site before the confirm button

#### Scenario: Deleting removes the links
- **WHEN** the editor confirms the delete of a dataset no question is bound to
- **THEN** the dataset, its layer and its links are gone and the survey's map no longer lists the layer

#### Scenario: A bound question blocks the delete
- **WHEN** a question is bound to the dataset's layer and the editor confirms the delete
- **THEN** nothing is deleted and the page names the question

#### Scenario: A report reads the dataset
- **WHEN** a report block reads a survey's answers dataset
- **THEN** the dataset's page names the report among the places that use it
