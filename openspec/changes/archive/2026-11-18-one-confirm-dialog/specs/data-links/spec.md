## MODIFIED Requirements

### Requirement: Every place that uses a dataset is listed
The system SHALL list on a dataset's page every place that uses it: the survey that owns it,
surveys and site blocks that link it, questions bound to it, and reports whose blocks read it.
Deleting a workspace dataset SHALL be offered on that page, under the list, and SHALL ask through
the app's confirmation dialog; it SHALL be refused while a question is bound to it — the page then
names the question instead of offering Delete — and SHALL remove its links otherwise.

#### Scenario: The delete page lists the places
- **WHEN** an editor opens the page of a dataset linked into a survey and a Site
- **THEN** the page names the survey and the site above the Delete button, which asks through the dialog

#### Scenario: Deleting removes the links
- **WHEN** the editor confirms the delete of a dataset no question is bound to
- **THEN** the dataset, its layer and its links are gone and the survey's map no longer lists the layer

#### Scenario: A bound question blocks the delete
- **WHEN** a question is bound to the dataset's layer
- **THEN** the page names the question instead of offering Delete, and a delete posted anyway deletes nothing

#### Scenario: A report reads the dataset
- **WHEN** a report block reads a survey's answers dataset
- **THEN** the dataset's page names the report among the places that use it
