## MODIFIED Requirements

### Requirement: Respondents can search the map for a place

Every survey map presented to a respondent SHALL offer a place search. It SHALL be present without
any configuration by the creator, on every published survey, including surveys published before this
capability existed.

The search SHALL find **points of interest** — named parks, squares, stations, venues, shops and
public buildings — as well as addresses, streets and settlements. A respondent SHALL be able to find
a place by the name they would use for it in conversation, without knowing its street address.

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

#### Scenario: Addresses remain findable

- **WHEN** a respondent searches for a street address
- **THEN** that address appears in the results, as it did before points of interest were added

#### Scenario: A creator does not have to enable it

- **WHEN** a survey published before this capability shipped is opened by a respondent
- **THEN** the place search is available, with no change made to that survey

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
