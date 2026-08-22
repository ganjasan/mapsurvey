## ADDED Requirements

### Requirement: Top-of-funnel acquisition block

The dashboard SHALL render a section, positioned above the registration-onward stages, showing for
a selected date window: Google impressions, landing visits, registrations, and demo opens. Each
stage SHALL display its absolute count and, except for the first, its conversion rate from the
preceding stage. The section SHALL state the date window it covers and name the source of each
stage.

#### Scenario: The four stages render with conversions

- **WHEN** a staff user opens the dashboard with all sources synchronised
- **THEN** the acquisition section shows impressions, landing visits, registrations, and demo opens
  for the window, with a conversion percentage between each consecutive pair

#### Scenario: Registrations agree with the cohort funnel

- **WHEN** the registrations stage is computed for a window
- **THEN** it counts the same real registrations (staff and superusers excluded) that the cohort
  funnel counts for that period

#### Scenario: The window and sources are stated

- **WHEN** the acquisition section renders
- **THEN** it states the covered date range and identifies which stage comes from Search Console,
  which from Plausible, and which from our own database

#### Scenario: Cross-source ratios are labelled as such

- **WHEN** conversion percentages between stages are shown
- **THEN** the section indicates that they combine separate measurement systems and do not track
  individual visitors through the funnel

### Requirement: Acquisition stages reflect source availability

Each acquisition stage SHALL be rendered from locally stored metrics only. A stage whose source is
not configured, has never synchronised, or has no data for the window SHALL render as unavailable
with the reason, and SHALL NOT render as zero. Any conversion rate depending on an unavailable
stage SHALL also render as unavailable.

#### Scenario: A source is not configured

- **WHEN** the dashboard renders while a provider has no credentials configured
- **THEN** that provider's stages show a not-configured note instead of a number, and the remaining
  stages and the rest of the dashboard render normally

#### Scenario: A source is configured but failing

- **WHEN** a provider's last synchronisation failed
- **THEN** the section shows that the data is stale, how old the last successful synchronisation is,
  and the reported failure

#### Scenario: A missing stage does not fabricate a conversion

- **WHEN** landing visits are unavailable for the window
- **THEN** the impressions-to-visits and visits-to-registrations rates render as unavailable rather
  than as 0% or as a rate computed against a missing value

#### Scenario: An empty but healthy window shows zero

- **WHEN** a source synchronised successfully and genuinely recorded no activity in the window
- **THEN** the stage shows zero, distinguishable from the unavailable state

### Requirement: Demo opens reported as total plus authentication split

The dashboard SHALL report demo opens as a total derived from all non-deleted sessions on the demo
survey, and separately as anonymous versus signed-in counts derived from recorded demo-open
entries. The split SHALL state the date from which it has been recorded, and SHALL NOT be presented
as covering sessions that predate that date.

#### Scenario: Total covers full history

- **WHEN** the demo total is computed for a window predating the split's start
- **THEN** it counts the demo survey's non-deleted sessions in that window

#### Scenario: The split is bounded by its start date

- **WHEN** the anonymous and signed-in counts are shown
- **THEN** the section states the date recording began, and does not attribute earlier sessions to
  either group

#### Scenario: The demo survey is identified

- **WHEN** the demo panel renders with a resolvable demo survey
- **THEN** it names the survey the numbers refer to

#### Scenario: The demo survey cannot be resolved

- **WHEN** the demo survey URL is unset or points at a survey that no longer exists
- **THEN** the demo stage renders as not configured and the rest of the dashboard renders normally

### Requirement: Acquisition channel breakdown

The dashboard SHALL show landing visits broken down by referrer channel for the selected window,
ordered by volume, so the traffic mix behind the visits stage is visible.

#### Scenario: Channels are listed by volume

- **WHEN** the window contains visits from several referrer channels
- **THEN** each channel is listed with its visit count, ordered from largest to smallest

#### Scenario: No channel data available

- **WHEN** the channel source is unavailable for the window
- **THEN** the breakdown renders as unavailable with the reason, and the rest of the section still
  renders

### Requirement: Synchronisation freshness is visible on the dashboard

The dashboard SHALL show, per external source, when it last synchronised successfully, so that a
silently stalled scheduled job is apparent to whoever reads the numbers.

#### Scenario: Freshness is shown next to the numbers

- **WHEN** the acquisition section renders with at least one configured source
- **THEN** it shows the age of that source's last successful synchronisation

#### Scenario: Stale data is flagged

- **WHEN** a configured source has not synchronised successfully for longer than the expected
  interval
- **THEN** the section marks that source's data as stale

## MODIFIED Requirements

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
`SurveySession`.

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
