## ADDED Requirements

### Requirement: Respondents can search the map for a place

Every survey map presented to a respondent SHALL offer a place search. It SHALL be present without
any configuration by the creator, on every published survey, including surveys published before this
capability existed.

#### Scenario: The search control is present on a survey map

- **WHEN** a respondent opens any section of any published survey
- **THEN** a place-search input is available on the map

#### Scenario: Searching moves the map

- **WHEN** a respondent selects a result from the search
- **THEN** the map view moves to that place

#### Scenario: A creator does not have to enable it

- **WHEN** a survey published before this capability shipped is opened by a respondent
- **THEN** the place search is available, with no change made to that survey

### Requirement: Searching never records an answer

Selecting a search result SHALL change the map viewport only. It SHALL NOT create, modify or delete
any answer, SHALL NOT place a marker or any other geometry, and SHALL NOT begin a drawing or editing
interaction.

#### Scenario: No geometry is created by searching

- **WHEN** a respondent searches for a place and selects a result on a section containing a point,
  line or polygon question
- **THEN** the map moves to that place, no marker or shape appears, and the question's answer is
  unchanged

#### Scenario: Searching does not interrupt an answer in progress

- **WHEN** a respondent has already placed a point and then searches for another place
- **THEN** the placed point is retained and the map moves

### Requirement: One geocoder serves every map on the platform

Every place search on the platform — respondent-facing and creator-facing — SHALL be served by the
same geocoding client, using the same provider and the same result behaviour. A place that one
surface can find SHALL be findable on the other.

#### Scenario: Editor and survey resolve the same query the same way

- **WHEN** the same query is entered in the creation page's map search and in a survey's map search,
  with the same map centre
- **THEN** both offer the same results in the same order

#### Scenario: Results are offered as a list, not assumed

- **WHEN** a respondent or creator types a query matching several places
- **THEN** the matching places are presented as a list to choose from, and the map moves only once a
  result is chosen

### Requirement: Geocoding requests are bounded

The search SHALL NOT issue a geocoding request for a query shorter than three characters, SHALL wait
for a pause in typing before issuing one, SHALL reuse a previously fetched result for a repeated
query within the same page session, and SHALL abandon an in-flight request when a newer query
supersedes it.

#### Scenario: Short queries are not sent

- **WHEN** a respondent has typed fewer than three characters
- **THEN** no geocoding request is made

#### Scenario: Typing continuously issues one request, not one per keystroke

- **WHEN** a respondent types a query without pausing
- **THEN** a single geocoding request is made, for the query as it stands after typing stops

#### Scenario: A repeated query is not re-fetched

- **WHEN** a respondent searches a query, then returns to the same query on the same page
- **THEN** the previous results are reused without a new request

### Requirement: Results are biased to the survey's map and language

A geocoding request SHALL bias results toward the current map centre and SHALL request results in
the respondent's active language.

#### Scenario: An ambiguous local name resolves nearby first

- **WHEN** a respondent searches a street name that exists in many places, on a map centred on their
  town
- **THEN** the nearest matching place is offered before more distant ones

### Requirement: Geocoding results are not retained

The platform SHALL NOT persist geocoding results. A searched place SHALL NOT be written to any
answer, session or log record.

#### Scenario: Searching leaves no stored trace

- **WHEN** a respondent searches for a place and submits the section
- **THEN** no geocoded place name or coordinate from the search is stored in the session's answers

### Requirement: The search is absent when no geocoder is configured

Where the deployment has no geocoding credentials, the search control SHALL NOT be rendered. It
SHALL NOT appear in a non-functional state.

#### Scenario: No token, no control

- **WHEN** a survey map is opened on a deployment with no Mapbox access token configured
- **THEN** no place-search input appears, and the map behaves as it does today
