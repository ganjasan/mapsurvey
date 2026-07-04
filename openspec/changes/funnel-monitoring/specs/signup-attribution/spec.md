## ADDED Requirements

### Requirement: Capture signup source at registration
The system SHALL capture the acquisition source of a new creator — the HTTP referrer (classified
into a source bucket) and any UTM parameters (`utm_source`, `utm_medium`, `utm_campaign`) present
on the landing/registration flow — and SHALL persist it associated with the created user on
successful registration.

#### Scenario: Referrer and UTM captured on successful registration
- **WHEN** a visitor arrives with a referrer and/or UTM parameters and completes registration
- **THEN** a `SignupAttribution` record is created for the new user storing the raw referrer, the
  classified source bucket, and the UTM triple

#### Scenario: Direct visit with no referrer
- **WHEN** a visitor registers with no referrer and no UTM parameters
- **THEN** a `SignupAttribution` record is created with an empty/`direct` source and null UTM fields
  (absence of source is recorded, not an error)

#### Scenario: UTM parsing reuses existing helpers
- **WHEN** UTM parameters are read from the landing request
- **THEN** the system uses the existing `store_utm_in_session` / `_consume_utm_from_session`
  helpers and the existing `_classify_referrer` helper rather than duplicating parsing logic

### Requirement: Attribution capture never blocks a signup
Signup-source capture SHALL be fail-open: any error while reading, classifying, or persisting the
source SHALL be swallowed so that registration always completes.

#### Scenario: Persistence error does not fail registration
- **WHEN** creating the `SignupAttribution` record raises an exception
- **THEN** the registration still succeeds and the user account is created without attribution data

### Requirement: Signups-by-source breakdown on the dashboard
The funnel dashboard SHALL display a breakdown of registrations grouped by captured source bucket,
so signups can be attributed to channels from the ship date onward.

#### Scenario: Source breakdown renders
- **WHEN** a staff user opens the dashboard after attribution is live
- **THEN** the page shows registration counts grouped by source bucket (including a `direct`/unknown group)

#### Scenario: Historical signups appear under unknown source
- **WHEN** the breakdown includes users registered before attribution shipped
- **THEN** those users are grouped under an unknown/`direct` bucket (no retro-active source is fabricated)
