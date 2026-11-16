## ADDED Requirements

### Requirement: Completed over the API means every visible required question answered
The API SHALL count completion the Responses overview's way. The response summary's `completed`
and `completion_rate`, and `completed_only` on the summary, text-answers, per-question GeoJSON and
export-link routes (and the MCP tools built on them), SHALL use the completion definition of `responses-required-unanswered` through the same shared
helper as the Responses overview and the export. Parameter descriptions in the OpenAPI document
and the MCP tool schemas SHALL say "responses that answered every required question", and the
generated help references SHALL be regenerated.

#### Scenario: Summary agrees with the Overview
- **WHEN** the Overview shows 3 completed of 5 for a survey
- **THEN** `GET /surveys/{uuid}/responses/summary` reports `completed: 3` and `completion_rate`
  60

#### Scenario: Removed validation settings are refused
- **WHEN** a question write sends `validation_settings.outlier_sigma`
- **THEN** the response is `422 validation` naming the field
