# Spec Delta

## Purpose

One checkbox per client on the creator's dossier — whether we have reached out to them, when
and with what outcome — so the daily signals, the digest and the dashboard never make the
owner write to the same person twice by accident, and the result of outreach is countable.

## ADDED Requirements

### Requirement: Every creator carries a worked flag
The creator's dossier SHALL hold a `worked` flag, the date it was set and an outcome from
`no_reply`, `declined`, `story`, `pro` (empty until known). Absent dossier SHALL read as not
worked. The flag SHALL be staff-only and never shown to the creator.

#### Scenario: Default
- **WHEN** a creator has no dossier or a dossier never marked
- **THEN** they read as not worked, with no date and no outcome

#### Scenario: Marking records the date
- **WHEN** staff tick the flag
- **THEN** the date is set to that day unless a date was given

### Requirement: The flag is editable as a checkbox in the admin list
The staff user list SHALL show the flag as an editable checkbox column with the date and
the outcome, filterable by worked / not worked and by outcome, and the dossier inline SHALL
show the same three fields.

#### Scenario: Bulk tick from the list
- **WHEN** staff tick the checkbox on three rows and save the list
- **THEN** the three creators are marked with today's date

#### Scenario: Filter not worked
- **WHEN** staff filter the list by not worked
- **THEN** only creators without the flag are listed

### Requirement: The flag is pre-filled from the dossier timeline
A one-off, re-runnable pre-fill SHALL mark as worked every creator whose timeline holds at
least one `email` note, dated by the earliest such note, and SHALL never clear a flag or
overwrite a date or an outcome set by hand.

#### Scenario: Creator with an imported sent email
- **WHEN** the pre-fill runs for a creator with an `email` note dated 2026-03-04 and no flag
- **THEN** the creator is marked worked as of 2026-03-04

#### Scenario: Hand-set date wins
- **WHEN** the pre-fill runs for a creator already marked by hand with a later date
- **THEN** nothing changes

### Requirement: Every outreach surface shows the flag
Each report-stage signal, each digest line and each dashboard row SHALL show whether the
signal's creator is worked and since when.

#### Scenario: Dashboard row of a worked client
- **WHEN** the report-stage panel lists a signal whose creator was marked worked
- **THEN** the row shows the worked date and outcome
