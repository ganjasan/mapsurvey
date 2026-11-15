## ADDED Requirements

### Requirement: A dataset is linked into surveys and sites, not copied
The system SHALL let a survey owner add a public layer dataset of the workspace to the survey's
reference layers "From Data", and SHALL let a site editor show one in a Site map block. A link
SHALL read the dataset's own objects, so an edit of the dataset SHALL show on every survey and site
that links it. Per survey link, the owner SHALL choose which public fields the respondent's object
card shows.

#### Scenario: One dataset in two surveys and a Site
- **WHEN** a dataset is linked into two surveys and a Site map block and one of its objects is renamed
- **THEN** both surveys' layer GeoJSON and the Site block's GeoJSON carry the new name

#### Scenario: Card fields per link
- **WHEN** a survey link shows only the field `species`
- **THEN** that survey's object card lists `species` and no other dataset field

#### Scenario: A linked layer cannot be edited from the survey
- **WHEN** a survey owner posts a settings change for a layer the survey only links
- **THEN** the request is refused and the dataset is unchanged

### Requirement: Links are guarded
The system SHALL refuse to link a dataset that is not `public`, SHALL refuse to make a linked
dataset private, SHALL refuse to link into a survey a dataset above the survey layer caps
(5,000 objects or 10 MB) or beyond 10 layers per survey, and SHALL refuse to unlink a dataset a
question of the survey is bound to.

#### Scenario: A private dataset
- **WHEN** an owner links a private dataset into a survey or a Site map block
- **THEN** the link is refused with a message saying to make the dataset public first

#### Scenario: Making a linked dataset private
- **WHEN** an editor sets a linked dataset to private
- **THEN** the change is refused and the page names the places that use it

#### Scenario: Above the caps
- **WHEN** an owner links a dataset of 6,000 objects into a survey
- **THEN** the link is refused naming the 5,000-object limit

#### Scenario: Unlinking a bound dataset
- **WHEN** an "Objects on the map" question of the survey is bound to the linked layer and the owner unlinks it
- **THEN** the unlink is refused naming the question

### Requirement: Every place that uses a dataset is listed
The system SHALL list on a dataset's page every place that uses it: the survey that owns it,
surveys and site blocks that link it, and questions bound to it. Deleting a workspace dataset SHALL
show that list before the delete is confirmed, SHALL be refused while a question is bound to it,
and SHALL remove its links otherwise.

#### Scenario: The delete page lists the places
- **WHEN** an editor opens the delete page of a dataset linked into a survey and a Site
- **THEN** the page names the survey and the site before the confirm button

#### Scenario: Deleting removes the links
- **WHEN** the editor confirms the delete of a dataset no question is bound to
- **THEN** the dataset, its layer and its links are gone and the survey's map no longer lists the layer

#### Scenario: A bound question blocks the delete
- **WHEN** a question is bound to the dataset's layer and the editor confirms the delete
- **THEN** nothing is deleted and the page names the question

### Requirement: Linked layers keep the memory rules
The system SHALL serve a linked layer's geometry only from gated GeoJSON endpoints; no survey or
site page SHALL inline a dataset's features.

#### Scenario: The Site page
- **WHEN** a visitor opens a published Site whose map block shows a dataset
- **THEN** the page carries the block's GeoJSON URL and none of the dataset's coordinates
