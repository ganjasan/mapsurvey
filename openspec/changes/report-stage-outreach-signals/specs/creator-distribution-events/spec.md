# Spec Delta

## MODIFIED Requirements

### Requirement: Creator return-to-data actions are captured server-side
The system SHALL emit `responses_viewed` when a creator loads a survey's responses page and
`data_exported` (with `format`) when a creator downloads survey data or exports a survey
definition. Both SHALL go through `product_events.emit`, be attributed to the acting creator,
carry `survey_id`, and never block or alter the response. For a data download `format` SHALL be
the format the creator chose — `zip`, `xlsx`, `csv`, `gpkg`, `shp` or `kml` — and `zip` when the
request names none. The responses-page load and the data download SHALL additionally record a
return-activity row in the application database (capability `creator-return-activity`) through
the same helper, so the two can never disagree about what counts as a return; the survey
definition backup records no row.

#### Scenario: Responses page opened
- **WHEN** a creator opens the responses view of a survey
- **THEN** one `responses_viewed` event with `survey_id` is emitted for that request and a
  `responses_viewed` return-activity row for that day is recorded

#### Scenario: Data downloaded
- **WHEN** a creator downloads the responses ZIP with no `format` parameter
- **THEN** one `data_exported` event with `survey_id` and `format='zip'` is emitted, a
  `data_exported` return-activity row for that day is recorded, and the download is served
  unchanged

#### Scenario: Excel downloaded
- **WHEN** a creator downloads `?format=xlsx`
- **THEN** one `data_exported` event with `survey_id` and `format='xlsx'` is emitted

#### Scenario: Rejected format emits nothing
- **WHEN** a request names an unknown `format` and is answered 400
- **THEN** no `data_exported` event is emitted and no row is recorded

#### Scenario: Survey definition exported
- **WHEN** a creator downloads the survey.json backup
- **THEN** one `data_exported` event is emitted and no return-activity row is recorded

#### Scenario: PostHog unconfigured
- **WHEN** PostHog is disabled
- **THEN** no event is sent, the return-activity row is still recorded, and the page or download
  is served unchanged
