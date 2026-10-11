# Spec Delta

## Purpose

The application's own record of a creator returning to a survey's collected data — opening
the Responses page or exporting the data — kept per creator, survey, action and day so that
detection and outreach can read it without depending on the analytics vendor.

## ADDED Requirements

### Requirement: Return-to-data actions are recorded per day
The system SHALL record, in its own database, each creator's return to a survey's data as one
row per creator, canonical survey, action kind (`responses_viewed`, `data_exported`) and
calendar day (UTC), with a count of occurrences that day and the last occurrence time. A
second action of the same kind on the same day SHALL increment the count rather than add a
row. The row SHALL name the canonical survey even when the request addressed a version or a
draft copy.

#### Scenario: First Responses visit of the day
- **WHEN** a creator opens a survey's Responses page for the first time on a day
- **THEN** one `responses_viewed` row for that creator, survey and day exists with count 1

#### Scenario: Repeated visits the same day
- **WHEN** the same creator opens the same survey's Responses page again that day
- **THEN** the existing row's count is 2 and no second row is added

#### Scenario: Export of an archived version
- **WHEN** a creator downloads the data of an archived version of a survey
- **THEN** the `data_exported` row names the canonical survey, not the version

#### Scenario: Survey definition backup is not a data return
- **WHEN** a creator downloads the survey.json backup (`export_survey`)
- **THEN** no row is recorded, although the PostHog `data_exported` event is still emitted

### Requirement: Recording never affects the request
Recording SHALL happen in the request that served the page or the download and SHALL never
block, slow noticeably or alter the response: a database error while recording SHALL be
logged and swallowed. Nothing about a respondent SHALL be stored in the row.

#### Scenario: Database error while recording
- **WHEN** the insert fails
- **THEN** the Responses page or the download is served unchanged and the failure is logged

#### Scenario: Anonymous or non-collaborator request
- **WHEN** the request is not from a signed-in creator with access to the survey
- **THEN** no row is recorded (the access check already refused the request)

### Requirement: Rows follow the creator and the survey
Rows SHALL be deleted with the creator's account and with the survey (cascade), SHALL be
listed in the admin read-only, and SHALL appear in the GDPR creator export alongside the
dossier notes, since they are facts about an identifiable person.

#### Scenario: Survey purged
- **WHEN** a survey is permanently deleted
- **THEN** its return-activity rows are deleted with it

#### Scenario: Creator export
- **WHEN** staff run the creator export for a username
- **THEN** the output includes that creator's return-activity rows
