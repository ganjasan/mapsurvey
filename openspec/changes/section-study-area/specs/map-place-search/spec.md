## MODIFIED Requirements

### Requirement: Respondents can search the map for a place

Every survey map presented to a respondent SHALL offer a place search. It SHALL be present without
any configuration by the creator, on every published survey, including surveys published before this
capability existed.

The search SHALL look for places first — countries, regions, settlements, districts, streets,
squares and addresses — and SHALL offer them above points of interest. Points of interest — named
schools, parks, stations, venues, shops and public buildings — SHALL be looked up only when no place
answers the query (no place returned is named after what was asked for). A respondent SHALL be able
to find a place by the name they would use for it in conversation, without knowing its street address.

When no place answers the query, the search SHALL consult the primary geocoder for every kind of
result and a secondary, OpenStreetMap-backed source. Areas the secondary source knows — districts,
quarters, administrative boundaries — SHALL be offered first. Its points of interest SHALL be offered
above the primary results only when the primary results do not answer the query either.

Where a place answers the query, neither the points-of-interest lookup nor the secondary source SHALL
be consulted automatically; the list SHALL end with a "More results" row that, when chosen, looks up
points of interest from both sources and the secondary source's areas and adds them below the places.

#### Scenario: The search control is present on a survey map

- **WHEN** a respondent opens any section of any published survey
- **THEN** a place-search input is available on the map

#### Scenario: Searching moves the map

- **WHEN** a respondent selects a result from the search
- **THEN** the map view moves to that place

#### Scenario: A city is found before venues named after it

- **WHEN** a creator searches "Санкт-Петербург" and the city has many venues whose names start with it
- **THEN** the city is the first result and no venue is listed

#### Scenario: More results finds the rare venue

- **WHEN** a creator searches "Санкт-Петербург", sees the city and a "More results" row, and chooses that row
- **THEN** venues named after the city are added below it and the city stays first

#### Scenario: A named point of interest is findable

- **WHEN** a respondent searches for a named school, park or station near the survey's map area that no place is named after
- **THEN** that place appears in the results

#### Scenario: A district the primary geocoder does not know is found

- **WHEN** a creator searches "Василеостровский район", which the primary geocoder has no area for but OpenStreetMap does
- **THEN** the district from OpenStreetMap is the first result, above venues that mention it

#### Scenario: A place the primary geocoder does not know is still found

- **WHEN** a respondent searches for a named place that the primary geocoder has no point of
  interest for, but which OpenStreetMap knows
- **THEN** that place appears in the results

#### Scenario: Addresses remain findable

- **WHEN** a respondent searches for a street address
- **THEN** that address appears in the results, resolved by the primary geocoder

#### Scenario: The fallback does not repeat what is already listed

- **WHEN** the secondary source returns a place at effectively the same position as a result already
  in the list
- **THEN** that entry is not added to the list

#### Scenario: An answered query costs no second request

- **WHEN** the places lookup returns a result named after what was searched for — a settlement for a
  settlement's name, a street for a street's name
- **THEN** no further request is made and that result stays at the top of the list

#### Scenario: A response full of look-alike results is not an answer

- **WHEN** no place answers the query and every point of interest the primary geocoder returns merely
  mentions the searched name inside a longer, unrelated name
- **THEN** the places the secondary source finds are offered above them

#### Scenario: A creator does not have to enable it

- **WHEN** a survey published before this capability shipped is opened by a respondent
- **THEN** the place search is available, with no change made to that survey

### Requirement: Results are biased to the survey's map and language

A geocoding request SHALL bias results toward the current map centre, and SHALL rank streets,
addresses and points of interest by whether their name starts with what was typed and then by
distance from it, only while that centre means something: a respondent's map framed by the creator,
a creator's own location, a place their brief names, the workspace's last survey, or any move of the
map by hand. From a default start nobody chose — a country centroid or the whole world — results
SHALL NOT be biased or ranked by distance. Settlements and administrative areas SHALL keep the
provider's order. A geocoding request SHALL request results in the respondent's active language — unless the query is written in another alphabet than that
language, in which case it SHALL request results in the language of the query's alphabet (Cyrillic:
Russian; Latin: English; Greek: Greek), so that places are named as they were typed.

#### Scenario: An ambiguous local name resolves nearby first

- **WHEN** a respondent searches a street name that exists in many places, on a map centred on their
  town
- **THEN** the nearest matching place is offered before more distant ones

#### Scenario: A default start does not rank

- **WHEN** a creator whose map opened on their country's centroid searches "Невский проспект" without moving the map
- **THEN** no proximity is sent and the provider's order is kept; after they drag the map to Saint Petersburg the street there is first

#### Scenario: A city typed in another alphabet

- **WHEN** a creator on an English page types "Санкт-Петербург"
- **THEN** the city is offered as "Санкт-Петербург", first, and no further request is made
