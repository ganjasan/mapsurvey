## MODIFIED Requirements

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
