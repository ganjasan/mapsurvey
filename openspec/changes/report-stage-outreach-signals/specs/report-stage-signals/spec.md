# Spec Delta

## Purpose

Tells the owner which surveys are entering the reporting stage and whose creators are worth
reaching out to with a materials archive and a story offer: the scoring rules, the
once-per-survey signal record with its outreach status, and the daily deliveries.

## ADDED Requirements

### Requirement: Surveys are scored daily against a sub-signal table
Once a day the system SHALL score every published or closed survey owned by a real,
non-staff account by summing the weights of the sub-signals present, read from one table in
code (name, weight, window). A survey SHALL be eligible only above a minimum number of
non-empty external responses in clean sessions, counted across the canonical survey and all
its versions. Draft, testing, archived and trashed surveys, the demo survey and surveys
with no owner SHALL be skipped.

#### Scenario: Below the volume floor
- **WHEN** a published survey has fewer non-empty external responses than the floor
- **THEN** it is not scored, whatever other sub-signals are present

#### Scenario: Staff-owned survey
- **WHEN** a survey is owned by a staff account
- **THEN** it is never scored

#### Scenario: Versions count together
- **WHEN** a survey's responses are split over a canonical row and two archived versions
- **THEN** the floor and every sub-signal are evaluated over the union

### Requirement: Behavioural sub-signals
The behavioural sub-signals SHALL be: `exported` (a data export by the owner or a collaborator
within the window), `closed` (status changed to closed within the window), `plateau`
(responses in the last 7 days below a fraction of the best week, after at least 14 days of
collection) and `revisited` (Responses opened on at least two distinct days within the
window). Each SHALL be defined by one condition and one window in the sub-signal table.

#### Scenario: Plateau after a launch spike
- **WHEN** a survey collected 80 responses in its best week three weeks ago and 5 in the last 7 days
- **THEN** `plateau` is present

#### Scenario: Still collecting
- **WHEN** a survey's last 7 days are its best week so far
- **THEN** `plateau` is absent

#### Scenario: Closed last month
- **WHEN** the status change to closed is older than the window
- **THEN** `closed` is absent

### Requirement: Profile sub-signals
The profile sub-signals SHALL be: `geo_rich` (at least a set number of placed geo features
across the survey's versions), `institutional` (creator in a municipality, consultancy, NGO or
university cohort, or on a non-freemail email domain) and `pro_interest` (a Pro questionnaire
answer by the creator's account or email). They describe who the creator is, carry the
smallest weights, and SHALL never fire a signal without a behavioural sub-signal.

#### Scenario: Institutional by domain only
- **WHEN** a creator has no cohort assignment but a non-freemail email domain
- **THEN** `institutional` is present

#### Scenario: Freemail creator without cohort
- **WHEN** a creator has no cohort assignment and a freemail address
- **THEN** `institutional` is absent

### Requirement: A data export fires on its own
With the volume floor met, the `exported` sub-signal SHALL fire the signal by itself,
regardless of the total score, because an export means the creator is building the report
now. Every other combination SHALL fire only when the summed weights reach the threshold.

#### Scenario: Export on a mid-size survey
- **WHEN** the owner of an eligible survey with no other sub-signal exports its data
- **THEN** the next daily run fires the signal with `exported` as its only sub-signal

#### Scenario: Weak sub-signals under the threshold
- **WHEN** an eligible survey has only `institutional` and `geo_rich`
- **THEN** no signal fires

### Requirement: One signal per survey, enriched on later runs
A survey SHALL fire at most once: the firing creates one signal record holding the canonical
survey, the creator, the score, the sub-signals with the values that triggered them, and the
firing time. A later run that finds new sub-signals on a survey that already fired SHALL add
them to the record and never create a second one or send a second digest line for it.

#### Scenario: Export after a plateau firing
- **WHEN** a survey fired on `plateau` + `revisited` and its owner exports the data a week later
- **THEN** the record gains `exported`, its status is unchanged and no new digest line is sent

#### Scenario: Re-run the same day
- **WHEN** the daily run executes twice
- **THEN** the second run creates nothing and sends nothing

### Requirement: Staff work the signal through a status
Each signal record SHALL carry a status from `new`, `contacted`, `dismissed`, `won`, editable
by staff in the admin together with a free-text note, and the admin list SHALL filter by
status and link to the creator's dossier, the survey and the Responses page. The record
SHALL hold ids and counts only — no respondent data, no answer text.

#### Scenario: Marking contacted
- **WHEN** staff set a signal to `contacted`
- **THEN** it leaves the "new" filter and keeps its sub-signals and firing time

#### Scenario: Dismissed survey stays quiet
- **WHEN** a signal is `dismissed` and later runs find further sub-signals
- **THEN** the sub-signals are added and the status stays `dismissed`

### Requirement: Every firing is delivered three ways
A firing SHALL (1) append a `signal` note to the creator's dossier timeline, idempotent by
source path so a re-run never duplicates it, (2) emit the product event
`outreach_signal_fired` with the survey id, the score and the sub-signal names, and (3) be
listed in that run's digest mail.

#### Scenario: Two firings in one run
- **WHEN** two surveys fire on the same run
- **THEN** one mail with two entries is sent, two dossier notes and two events are written

#### Scenario: Nothing fired
- **WHEN** a run fires no signal
- **THEN** no mail is sent

#### Scenario: Mail failure does not lose the signal
- **WHEN** the digest cannot be sent
- **THEN** the signal records, notes and events still exist and the failure is logged

### Requirement: One digest per run, only when something fired
The daily run SHALL send one digest to the configured outreach address only when at least one
signal fired. For each signal it SHALL name the survey, the creator (username, organisation
if recorded, segment cohort), the response count, the sub-signals with their values, and deep
links to the signal's admin page, the creator's dossier and the survey's Responses page.

#### Scenario: Digest content
- **WHEN** a signal fired on `exported` and `institutional` for a survey with 120 responses
- **THEN** the digest names both sub-signals, the count and the three links

### Requirement: The detector can be dry-run as of a past date
The run SHALL accept a dry-run mode that writes nothing and sends nothing but prints what
would fire, and an as-of date that evaluates every window and the volume floor as they stood
on that date, so the weights can be checked against surveys the owner already contacted.

#### Scenario: Dry run as of a past date
- **WHEN** the detector is run in dry-run mode as of a date two months ago
- **THEN** it lists the surveys that would have fired by then, with their sub-signals, and no record, note, event or mail is created

### Requirement: Detection fails open and never touches creators or respondents
A failure while scoring one survey SHALL be logged and SHALL NOT stop the run for the
others. The detector SHALL write nothing a creator or respondent can see and SHALL NOT
change any survey.

#### Scenario: One survey raises
- **WHEN** scoring one survey throws
- **THEN** the remaining surveys are scored, the error is logged and the digest covers the ones that fired
