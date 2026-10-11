# Spec Delta

## MODIFIED Requirements

### Requirement: Action lists
The dashboard SHALL show three actionable lists with deep links into the admin:
institutional-domain registrants who never created a survey (outreach candidates), surveys
collecting responses while still draft/testing (publish-nudge candidates), and surveys that
entered the reporting stage (report-outreach candidates: open signals from capability
`report-stage-signals` with status `new` or `contacted`, newest first, each with the creator,
the sub-signals, the response count, the status and links to the signal's admin page, the
creator's dossier and the survey).

#### Scenario: Dormant valuable list
- **WHEN** a registrant has a non-freemail email domain and owns no survey
- **THEN** they appear in the dormant-valuable list with a link to their admin page

#### Scenario: Collecting-but-unpublished list
- **WHEN** a draft or testing survey has at least one non-deleted response
- **THEN** it appears in the collecting-but-unpublished list with a link to the survey

#### Scenario: Report-stage list
- **WHEN** a survey has a report-stage signal with status `new`
- **THEN** it appears in the report-stage list with its sub-signals and a link to the signal

#### Scenario: Worked signals leave the list
- **WHEN** a signal's status is `dismissed` or `won`
- **THEN** it no longer appears in the report-stage list

### Requirement: No new data table for the funnel dashboard
The **registration-onward** stages of the funnel SHALL be computed live from existing tables
(`auth_user`, `SurveyHeader`, `SurveySection`, `Question`, `SurveySession`) and SHALL NOT require a
new data-bearing table or a data backfill for those stages. A metadata-only migration for the
display proxy model (no DDL, no table) is permitted.

This constraint applies to everything derivable from our own rows. It SHALL NOT apply to the
pre-registration acquisition stages, which are not derivable from our tables at all: impressions and
landing visits exist only inside third-party systems, and a staff page must not call those APIs
during a request. Those metrics SHALL therefore be persisted locally by an out-of-band sync, and the
respondent-identity needed to split demo opens SHALL live in its own table rather than being added to
`SurveySession`. Nor SHALL it apply to forward-only facts about creators that no existing row
records — a creator's return to a survey's data and the outreach signals derived from it — which
live in their own tables and whose panels state the date recording started.

#### Scenario: Dashboard reflects history on first deploy
- **WHEN** the dashboard is deployed for the first time with no prior instrumentation
- **THEN** the registration-onward stages display the full historical funnel computed from existing
  rows, with no backfill step

#### Scenario: No data-bearing schema change for derivable stages
- **WHEN** a stage can be computed from existing rows
- **THEN** it is computed live and no table is added to store it

#### Scenario: Externally sourced stages are persisted locally
- **WHEN** a stage's data exists only in a third-party analytics system
- **THEN** it is stored in a local table by a scheduled sync, and the dashboard reads that table
  instead of calling the provider during a request

#### Scenario: Forward-only stages state their start date
- **WHEN** a stage or breakdown cannot be reconstructed for the period before it began recording
- **THEN** the dashboard reports the date recording started rather than presenting the earlier period
  as if it had been measured
