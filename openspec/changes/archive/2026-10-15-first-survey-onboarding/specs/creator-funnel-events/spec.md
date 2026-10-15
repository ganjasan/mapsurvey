## ADDED Requirements

### Requirement: Survey creation records its surface and map source
The `survey_created` event SHALL carry `surface` — `start_blank` for the one-request
blank endpoint, `create_page` for both actions of `/editor/surveys/new/` — and
`map_source` as defined in `map-start-position` (`browser`, `org_survey`, `country`,
`world`, `creator`, `brief`). Neither property SHALL carry coordinates, a place name or
any creator-written text; `creation_method` is unchanged.

#### Scenario: Blank endpoint
- **WHEN** a survey is created through `/editor/surveys/new/blank/` with no browser position in an organization without positioned surveys and no resolvable country
- **THEN** `survey_created` carries `creation_method='manual'`, `surface='start_blank'`, `map_source='world'`

#### Scenario: Create page manual action
- **WHEN** a survey is created with the create page's manual action and an untouched map
- **THEN** `survey_created` carries `surface='create_page'` and the `map_source` posted by the page

#### Scenario: No coordinates in the payload
- **WHEN** any `survey_created` event is emitted
- **THEN** its properties contain no latitude, longitude, place name or country code

### Requirement: Agent access interest event
The system SHALL emit `agent_access_requested` once per creator, when
`CreatorPreferences.agent_access_requested_at` is first set from the agent access page,
attributed to the creator and carrying no further properties.

#### Scenario: First request emits
- **WHEN** a creator posts "Tell me when it's ready" for the first time
- **THEN** one `agent_access_requested` event is emitted for that creator

#### Scenario: Repeat request is silent
- **WHEN** the same creator posts it again
- **THEN** no event is emitted
