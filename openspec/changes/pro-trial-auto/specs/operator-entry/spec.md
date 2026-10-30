## MODIFIED Requirements

### Requirement: Operator entry is opened from Responses by editors of a Pro workspace
The Responses page SHALL offer *Enter a response* to members with the `editor` role or above on
the survey, marked with `{% pro_badge survey.organization "operator_entry" %}`. The entry header and
every entry URL SHALL be gated by the Pro feature `operator_entry` on the organisation that owns
the survey, checked per request through `billing.trial.may`: the plan includes it, a live trial
covers it, or the workspace is startable. Creating an operator session from the entry header SHALL
go through `billing.trial.use(org, "operator_entry", actor)`, which starts a startable trial and
counts the session; the trial puts no cap on entered sessions. The sections, the saved page and
uploads of an already created operator session SHALL be admitted while the feature is in force
(`covers`). When `may` is false the control SHALL render disabled with the locked mark linking to
the billing page and the entry URLs SHALL answer the standard feature refusal; sessions entered
while the feature was held SHALL remain.

#### Scenario: Editor of a Pro workspace opens the form
- **WHEN** an `editor` of a Pro organisation clicks *Enter a response* on Responses
- **THEN** the entry header renders and the control carries the quiet "Pro" mark

#### Scenario: Viewer cannot enter
- **WHEN** a `viewer` requests the entry header URL
- **THEN** the response is 403

#### Scenario: Editor of a startable Free workspace starts the trial with the first sheet
- **GIVEN** a Free organisation without a grant whose owner has not used a trial
- **WHEN** an `editor` opens Responses
- **THEN** *Enter a response* is enabled with the "Pro · free to try" mark
- **AND WHEN** the editor submits the entry header
- **THEN** the trial grant exists with `trigger = "operator_entry"` and `started_by` = the editor, the `operator_entry` allowance reads 1 used with no limit, and the first section renders

#### Scenario: Free workspace that cannot start a trial sees the lock
- **WHEN** an `editor` of a Free organisation whose trial has expired opens Responses
- **THEN** *Enter a response* is rendered disabled with the locked Pro mark linking to the billing page
- **AND** a request to the entry header URL answers the `require_feature` refusal

#### Scenario: Lapsed subscription keeps entered sessions
- **GIVEN** three sessions were entered while the organisation was Pro
- **WHEN** the entitlement lapses
- **THEN** the three sessions are still listed on Responses and the entry URLs refuse new entries

#### Scenario: Closed survey accepts entries
- **WHEN** an editor opens the entry header of a `closed` survey
- **THEN** the header renders — a closed survey is where sheets get entered
