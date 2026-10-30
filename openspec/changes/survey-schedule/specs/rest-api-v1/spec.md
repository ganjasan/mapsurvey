## ADDED Requirements

### Requirement: Survey period over the API
`GET /surveys` and `GET /surveys/{uuid}` SHALL include `opens_at`, `closes_at` (ISO 8601, UTC,
`null` when unset) and `schedule_timezone`. `PATCH /surveys/{uuid}` (scope `surveys:write`, role
`owner`) SHALL accept the three fields, a `null` clearing an instant, and SHALL validate them
through `SurveyHeaderForm` like every other Settings field, so a closing time before the opening
time or a changed closing time in the past answers `422 validation` naming `closes_at`. The
period SHALL be written on the canonical survey even when the uuid names unpublished changes.
`POST /surveys/{uuid}/publish` on a `closed` survey SHALL clear a past `closes_at` (capability
`survey-schedule`).

#### Scenario: Read and set
- **WHEN** an owner token PATCHes `{"opens_at": "2026-11-03T09:00:00+06:00",
  "closes_at": "2026-11-30T23:59:00+06:00", "schedule_timezone": "Asia/Bishkek"}`
- **THEN** the response is `200` with `opens_at: "2026-11-03T03:00:00Z"`,
  `closes_at: "2026-11-30T17:59:00Z"` and `schedule_timezone: "Asia/Bishkek"`

#### Scenario: Clear the end
- **WHEN** the same token PATCHes `{"closes_at": null}`
- **THEN** the response shows `closes_at: null` and `opens_at` unchanged

#### Scenario: Invalid order
- **WHEN** a PATCH sets `closes_at` earlier than the stored `opens_at`
- **THEN** the response is `422 validation` with `closes_at` among the named fields

#### Scenario: Unpublished changes write to the live survey
- **GIVEN** a published survey with unpublished changes
- **WHEN** a PATCH on the draft's uuid sets `closes_at`
- **THEN** the canonical survey holds it and the draft row holds nothing
