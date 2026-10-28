# map-place-search Specification

## Purpose
TBD - created by archiving change respondent-map-search. Update Purpose after archive.
## Requirements
### Requirement: Respondents can search the map for a place

Every survey map presented to a respondent SHALL offer a place search. It SHALL be present without
any configuration by the creator, on every published survey, including surveys published before this
capability existed.

The search SHALL find points of interest — named parks, squares, stations, venues, shops and public
buildings — as well as addresses, streets and settlements. A respondent SHALL be able to find a
place by the name they would use for it in conversation, without knowing its street address.

Where the primary geocoder does not answer the query — no result it returns is named after what was
asked for — the search SHALL consult a secondary, OpenStreetMap-backed source and add the points of
interest it finds. The secondary source SHALL only add results; it SHALL NOT replace or reorder the
primary ones, and SHALL NOT contribute administrative areas such as cities, districts or countries.

Where the primary geocoder does answer the query, the secondary source SHALL NOT be consulted.

#### Scenario: The search control is present on a survey map

- **WHEN** a respondent opens any section of any published survey
- **THEN** a place-search input is available on the map

#### Scenario: Searching moves the map

- **WHEN** a respondent selects a result from the search
- **THEN** the map view moves to that place

#### Scenario: A named point of interest is findable

- **WHEN** a respondent searches for a named park, station or venue that exists near the survey's
  map area
- **THEN** that place appears in the results

#### Scenario: A place the primary geocoder does not know is still found

- **WHEN** a respondent searches for a named place that the primary geocoder has no point of
  interest for, but which OpenStreetMap knows
- **THEN** that place appears in the results

#### Scenario: Addresses remain findable

- **WHEN** a respondent searches for a street address
- **THEN** that address appears in the results, resolved by the primary geocoder

#### Scenario: The fallback does not repeat what the primary already answered

- **WHEN** the secondary source returns a place at effectively the same position as a result already
  in the list, or returns an administrative area such as a city
- **THEN** that entry is not added to the list

#### Scenario: An answered query costs no second request

- **WHEN** the primary geocoder returns a result named after what was searched for — a settlement
  for a settlement's name, a venue for that venue's name
- **THEN** the secondary source is not consulted, and that result stays at the top of the list

#### Scenario: A response full of look-alike results is not an answer

- **WHEN** every result the primary geocoder returns merely mentions the searched name inside a
  longer, unrelated name
- **THEN** the secondary source is consulted, and the places it finds are offered above them

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

### Requirement: Results are offered as a list, not assumed

Every place search on the platform — respondent-facing and creator-facing — SHALL be served by the
same geocoding client, using the same provider and the same result behaviour. A place that one
surface can find SHALL be findable on the other.

Where the provider identifies a result as a point of interest and states its category, the result
SHALL display that category, so that two places sharing a name can be told apart before one is
chosen.

#### Scenario: Editor and survey resolve the same query the same way

- **WHEN** the same query is entered in the creation page's map search and in a survey's map search,
  with the same map centre
- **THEN** both offer the same results in the same order

#### Scenario: Results are offered as a list

- **WHEN** a respondent or creator types a query matching several places
- **THEN** the matching places are presented as a list to choose from, and the map moves only once a
  result is chosen

#### Scenario: A point of interest shows what kind of place it is

- **WHEN** the results include a point of interest whose category the provider reports
- **THEN** that row displays the category alongside the place name and its location

#### Scenario: A result without a category shows none

- **WHEN** a result carries no category — an address, a street, a settlement
- **THEN** that row displays name and location only, with no empty or placeholder category

### Requirement: The search degrades rather than breaks

Failure of the secondary source SHALL be invisible to the respondent. If it errors, does not answer
within a bounded time, or returns nothing usable, the search SHALL present the primary results
alone, with no error message and no delay beyond that bound.

#### Scenario: The secondary source is unavailable

- **WHEN** the secondary source cannot be reached or fails
- **THEN** the primary results are shown as normal, and no error is presented to the respondent

#### Scenario: The secondary source is slow

- **WHEN** the secondary source does not answer within the bounded wait
- **THEN** the primary results are shown without it

#### Scenario: No geocoder configured at all

- **WHEN** a survey map is opened on a deployment with no primary access token configured
- **THEN** no place-search input appears, and the secondary source is not consulted either

### Requirement: OpenStreetMap results are attributed

When the result list contains entries derived from OpenStreetMap, the list SHALL display
attribution to OpenStreetMap contributors. When it contains no such entries, no attribution SHALL be
shown.

#### Scenario: Attribution appears with OSM results

- **WHEN** the result list includes a place contributed by the OpenStreetMap-backed source
- **THEN** the list displays attribution to OpenStreetMap contributors

#### Scenario: No attribution without OSM results

- **WHEN** every result in the list came from the primary geocoder
- **THEN** no OpenStreetMap attribution is displayed

