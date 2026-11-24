## MODIFIED Requirements

### Requirement: A dataset is linked into surveys and sites, not copied
Every reference layer of a survey SHALL be a workspace layer dataset linked to the survey: a layer
uploaded or drawn from the survey SHALL be created in the workspace and linked, and a survey owner
SHALL be able to add any public layer dataset of the workspace "From Data". A site editor SHALL be
able to show one in a Site map block. A link SHALL read the dataset's own objects, so an edit of the
dataset SHALL show on every survey and site that links it. Linking a dataset into a survey SHALL NOT
by itself show it; its placement does (spec `map-layer-placement`), and *From Data* in the Map card
SHALL link and place in one step. Per survey link, the owner SHALL choose which public fields the
respondent's object card shows. Layers built from respondents' answers (`source='question'`) stay
owned by their survey. Deleting a survey SHALL NOT delete the layer datasets it linked.

#### Scenario: One dataset in two surveys and a Site
- **WHEN** a dataset is linked into two surveys and a Site map block and one of its objects is renamed
- **THEN** both surveys' layer GeoJSON and the Site block's GeoJSON carry the new name

#### Scenario: Card fields per link
- **WHEN** a survey link shows only the field `species`
- **THEN** that survey's object card lists `species` and no other dataset field

#### Scenario: An upload from the survey is a dataset
- **WHEN** a creator uploads a layer from a survey's Map card
- **THEN** Data lists the layer as a public workspace dataset whose "Used by" names the survey

#### Scenario: The survey is deleted
- **WHEN** a survey that linked an uploaded layer is deleted
- **THEN** the dataset stays in Data with an empty "Used by"

### Requirement: Links are guarded
The system SHALL refuse to link a dataset that is not `public`, SHALL refuse to make a linked
dataset private, SHALL refuse to link into a survey a dataset above the survey layer caps
(5,000 objects or 10 MB) or beyond 10 layers per survey, SHALL refuse to place a layer the survey
does not link, and SHALL refuse to unlink a dataset an Objects-on-the-map question of the survey
asks about.

#### Scenario: A private dataset
- **WHEN** an owner links a private dataset into a survey or a Site map block
- **THEN** the link is refused with a message saying to make the dataset public first

#### Scenario: Making a linked dataset private
- **WHEN** an editor sets a linked dataset to private
- **THEN** the change is refused and the page names the places that use it

#### Scenario: Above the caps
- **WHEN** an owner links a dataset of 6,000 objects into a survey
- **THEN** the link is refused naming the 5,000-object limit

#### Scenario: Unlinking a dataset that is asked about
- **WHEN** an "Objects on the map" question of the survey asks about the linked layer and the owner unlinks it
- **THEN** the unlink is refused naming the question
