## ADDED Requirements

### Requirement: Every dataset has a page with its details
The system SHALL give every dataset in the catalogue a page in the editor showing its source, its
facts and its details: name, description, theme (the DCAT-AP data themes), maintainer, update
frequency and licence. The licence SHALL be one of OGL v3, CC BY 4.0, CC0 and dl-de/by-2-0, or
unset. Workspace owners, admins and editors with access to the dataset SHALL edit the details;
viewers SHALL read them; a member without access to the dataset's survey SHALL get 404.

#### Scenario: An editor sets the licence
- **WHEN** a workspace editor opens an uploaded dataset's page and saves licence CC BY 4.0 and theme Environment
- **THEN** the dataset stores both and the page shows them

#### Scenario: A licence outside the list is refused
- **WHEN** a request posts the licence `gpl-3.0`
- **THEN** nothing is saved and the form names the field

#### Scenario: A viewer cannot edit
- **WHEN** a workspace viewer posts the details form
- **THEN** the request is refused and the dataset is unchanged

### Requirement: A layer dataset has an editable field dictionary
The system SHALL show, for a layer dataset, one row per field with its name, label, type,
description and a private switch, and SHALL save edits to them. A survey layer's dictionary SHALL
list the layer's property names even before anyone documented them.

#### Scenario: Labelling a field
- **WHEN** an editor sets the label of `TR_HGT_M` to "Tree height (m)"
- **THEN** the dictionary stores the label and the field keeps its name

#### Scenario: A survey layer's fields appear undocumented
- **WHEN** an editor opens the page of a survey layer whose objects carry `species`
- **THEN** the dictionary lists `species` with the label `species`

### Requirement: A private field never leaves the dataset's own editor
The system SHALL exclude a field marked private from every output other than the dataset page and
the object editor: the layer GeoJSON served to respondents, Responses and the API, object reads
over the REST API and MCP, the survey ZIP export, the dataset download, a layer's label field and
style rule, the editor's property pickers and value summaries, and a budget's cost property. A
write over the API SHALL NOT remove a private value it did not send.

#### Scenario: The respondent map
- **WHEN** a layer's `INSP_EMAIL` field is private and a respondent's map fetches the layer
- **THEN** no feature carries `INSP_EMAIL`

#### Scenario: The REST API and MCP
- **WHEN** an API client lists the layer's objects
- **THEN** no object's `properties` carries `INSP_EMAIL`

#### Scenario: The survey ZIP export
- **WHEN** the survey is exported as a ZIP
- **THEN** the layer's objects in it carry no `INSP_EMAIL`

#### Scenario: Pickers and summaries
- **WHEN** the editor lists the layer's property names or asks for the value summary of `INSP_EMAIL`
- **THEN** the field is not offered and the summary is empty

#### Scenario: An API write keeps the private value
- **WHEN** an API client replaces an object's `properties` with `{"species": "Oak"}`
- **THEN** the object keeps its private `INSP_EMAIL` value

#### Scenario: Making a field private takes effect at once
- **WHEN** an editor marks `species` private on a layer already served to respondents
- **THEN** the next layer GeoJSON carries no `species`

### Requirement: Labels replace raw field names where people read them
The system SHALL show a layer's public documented fields on the respondent's object card as label
and value, and SHALL write labels as the column names of the dataset download. Map styles and
label fields SHALL keep matching raw names.

#### Scenario: The object card
- **WHEN** a respondent opens an object whose layer labels `TR_HGT_M` as "Tree height (m)"
- **THEN** the card reads "Tree height (m)" with the object's value and never `TR_HGT_M`

#### Scenario: The download
- **WHEN** an editor downloads a labelled dataset as CSV
- **THEN** the header carries the labels and no private column
