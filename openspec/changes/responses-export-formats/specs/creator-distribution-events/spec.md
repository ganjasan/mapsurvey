## MODIFIED Requirements

### Requirement: Creator return-to-data actions are captured server-side
The system SHALL emit `responses_viewed` when a creator loads a survey's responses page and
`data_exported` (with `format`) when a creator downloads survey data or exports a survey
definition. Both SHALL go through `product_events.emit`, be attributed to the acting creator,
carry `survey_id`, and never block or alter the response. For a data download `format` SHALL be
the format the creator chose — `zip`, `xlsx`, `csv`, `gpkg`, `shp` or `kml` — and `zip` when the
request names none.

#### Scenario: Responses page opened
- **WHEN** a creator opens the responses view of a survey
- **THEN** one `responses_viewed` event with `survey_id` is emitted for that request

#### Scenario: Data downloaded
- **WHEN** a creator downloads the responses ZIP with no `format` parameter
- **THEN** one `data_exported` event with `survey_id` and `format='zip'` is emitted and the download
  is served unchanged

#### Scenario: Excel downloaded
- **WHEN** a creator downloads `?format=xlsx`
- **THEN** one `data_exported` event with `survey_id` and `format='xlsx'` is emitted

#### Scenario: Rejected format emits nothing
- **WHEN** a request names an unknown `format` and is answered 400
- **THEN** no `data_exported` event is emitted

#### Scenario: PostHog unconfigured
- **WHEN** PostHog is disabled
- **THEN** the views behave exactly as before and nothing is sent
