## ADDED Requirements

### Requirement: Staff-defined cohort vocabulary

The system SHALL store cohort dimensions and cohorts as data. A `CohortDimension`
SHALL have a unique slug, a display name and an ordering. A `Cohort` SHALL belong
to exactly one dimension and SHALL have a slug unique within that dimension, a
display name, an optional description and colour, and an ordering. Staff SHALL be
able to create, rename and reorder both without a code change or migration.

#### Scenario: Two cohorts may share a slug across dimensions

- **WHEN** a cohort with slug `other` exists in the `plan` dimension and a cohort
  with slug `other` is created in the `segment` dimension
- **THEN** both are created successfully.

#### Scenario: Duplicate slug within one dimension is rejected

- **WHEN** a second cohort with slug `free` is created in the `plan` dimension
- **THEN** the write fails with an integrity error.

### Requirement: At most one cohort per user per dimension

The system SHALL allow a user to hold at most one cohort within any single
dimension, enforced by a database constraint on (user, dimension). Assigning a
user a cohort in a dimension where they already hold one SHALL replace the
existing assignment rather than adding a second.

#### Scenario: User holds cohorts in two dimensions

- **WHEN** a user is assigned `plan=pro` and `segment=municipality`
- **THEN** both assignments exist and the user resolves to `pro` for the plan
  dimension and `municipality` for the segment dimension.

#### Scenario: Reassignment within a dimension replaces

- **GIVEN** a user assigned `segment=university`
- **WHEN** the same user is assigned `segment=consultancy`
- **THEN** exactly one assignment remains for the segment dimension and it points
  at `consultancy`.

#### Scenario: Assignment dimension follows its cohort

- **WHEN** an assignment is saved with a cohort belonging to the `segment`
  dimension
- **THEN** the assignment's dimension is that cohort's dimension, regardless of
  what the caller supplied.

### Requirement: Assignments record their origin and manual wins

Each assignment SHALL record a `source` of either `auto` (produced by a
classification rule) or `manual` (set by a staff member), and an `assigned_at`
timestamp. Automatic classification SHALL NOT create, modify or delete an
assignment whose source is `manual`.

#### Scenario: Classification skips a manually assigned user

- **GIVEN** a user with a `manual` segment assignment of `consultancy` and an
  email domain whose rule maps to `university`
- **WHEN** classification runs
- **THEN** the assignment still points at `consultancy` with source `manual`.

#### Scenario: Classification updates its own earlier guess

- **GIVEN** a user with an `auto` segment assignment of `university`
- **WHEN** the domain rules are changed so their domain maps to `government` and
  classification runs
- **THEN** the assignment points at `government` with source `auto`.

#### Scenario: Staff assignment overrides a rule result

- **GIVEN** a user with an `auto` segment assignment
- **WHEN** a staff member assigns them a different cohort in that dimension
- **THEN** the assignment points at the staff-chosen cohort with source `manual`.

### Requirement: Segment classification from email domain

The system SHALL propose a segment cohort for a user from their email domain,
using an exact-domain map first and domain-suffix rules second. A freemail domain
SHALL produce no proposal, leaving the user unclassified rather than assigning a
fallback cohort.

#### Scenario: Institutional academic domain maps to education

- **WHEN** classification evaluates a user with an `@sdsu.edu` or
  `@cardiff.ac.uk` address
- **THEN** the proposed segment is the university cohort.

#### Scenario: Government domain maps to municipality

- **WHEN** classification evaluates a user with an `@brent.gov.uk` or
  `@senmvku.berlin.de` address
- **THEN** the proposed segment is the municipality cohort.

#### Scenario: Curated domain overrides the suffix rule

- **WHEN** classification evaluates a user at a domain present in the curated map
- **THEN** the curated cohort is proposed even if a suffix rule would also match.

#### Scenario: Freemail yields no proposal

- **WHEN** classification evaluates a user with an `@gmail.com` address
- **THEN** no assignment is created for that user.

#### Scenario: Missing or malformed email yields no proposal

- **WHEN** classification evaluates a user with an empty or `@`-less email
- **THEN** no assignment is created and no error is raised.

### Requirement: Bulk classification command

The system SHALL provide a management command that applies segment classification
across all non-staff users. The command SHALL default to a dry run that reports
intended changes without writing, SHALL write only when explicitly told to, and
SHALL be safe to run repeatedly.

#### Scenario: Dry run writes nothing

- **WHEN** the command runs without the apply flag
- **THEN** it prints the proposed assignments and the database is unchanged.

#### Scenario: Second run is a no-op

- **GIVEN** the command has already been applied
- **WHEN** it is applied again with unchanged rules and users
- **THEN** no assignment is created, changed or deleted.

### Requirement: Curated bulk labelling from a list

The system SHALL accept a curated file mapping usernames to cohorts and apply it
as manual assignments, so that users whose email domain carries no signal can be
labelled in bulk rather than one at a time. Rows naming an unknown user or an
unknown cohort SHALL be reported and skipped without aborting the run.

#### Scenario: Curated row lands as a manual assignment

- **WHEN** a curated list naming a freemail user and a cohort is applied
- **THEN** that user holds the cohort with source `manual` and the row's note.

#### Scenario: Curated labels survive later rule runs

- **GIVEN** a user labelled from a curated list whose domain also matches a rule
- **WHEN** domain classification is applied afterwards
- **THEN** the curated label is unchanged.

#### Scenario: Unknown rows do not abort the run

- **WHEN** a curated list contains a row naming a user who does not exist and a
  row naming a cohort that does not exist, alongside a valid row
- **THEN** the two bad rows are reported and skipped and the valid row is applied.

### Requirement: Staff cohort administration

The system SHALL expose dimensions, cohorts and assignments in the Django admin
to staff users, and SHALL provide a bulk action on the user list that assigns a
chosen cohort to every selected user with source `manual`.

#### Scenario: Bulk action assigns selected users

- **WHEN** a staff member selects several users and applies the bulk action with
  a chosen cohort
- **THEN** every selected user holds that cohort in its dimension with source
  `manual`, replacing any previous assignment in that dimension.

#### Scenario: Non-staff cannot reach cohort administration

- **WHEN** a user who is not staff requests a cohort admin URL
- **THEN** access is denied.

### Requirement: Funnel dashboard cohort breakdown

The funnel dashboard SHALL present, for each cohort dimension, one row per cohort
plus an explicit row for users with no assignment in that dimension. Each row
SHALL report the number of users, how many created a survey, published a survey
and collected at least one response, and the total responses collected.

#### Scenario: Every registration appears exactly once per dimension

- **WHEN** the breakdown is computed for a dimension
- **THEN** the user counts of its cohort rows plus the unclassified row equal the
  total number of non-staff registrations.

#### Scenario: Dimension with no assignments still renders

- **GIVEN** a dimension whose cohorts have no assigned users
- **WHEN** the dashboard renders
- **THEN** the dimension is shown with all users in the unclassified row and no
  error is raised.

#### Scenario: Breakdown counts activation per cohort

- **GIVEN** a cohort holding two users, one of whom published a survey that
  collected responses
- **WHEN** the breakdown is computed
- **THEN** the cohort row reports two users, one published and one collecting.
