## ADDED Requirements

### Requirement: Every place dataset of a workspace is in the catalogue
The system SHALL keep a dataset registry per workspace in which every reference layer (uploaded or
drawn), every shared-map layer, every top-level geo question of a survey (by code across its
versions) and every survey's respondent rows appear as one dataset each, without moving any data.
A dataset collected by a survey SHALL default to the `aggregated` privacy class and a creator's
layer to `public`. A dataset whose source is gone SHALL leave the catalogue.

#### Scenario: Existing data appears without any action
- **WHEN** a workspace has a survey with a point question, an uploaded layer and answers, and a
  member opens Data for the first time
- **THEN** the catalogue lists the layer (public), the point question's answers (aggregated) and the
  survey's responses (aggregated)

#### Scenario: A removed question leaves the catalogue
- **WHEN** the point question is deleted from every version of the survey
- **THEN** its answers dataset is no longer listed

### Requirement: Members see only datasets of surveys they can access, as counts
The catalogue SHALL list a survey's datasets only to members who have a role on that survey
(workspace owners, admins and viewers have one on every survey; an editor on the surveys they
collaborate on). It SHALL show each dataset's source, number of rows, privacy class, how many
places use it and when it last changed — never an individual answer.

#### Scenario: Editor without access does not see another survey's data
- **WHEN** a workspace editor who does not collaborate on survey B opens Data
- **THEN** none of survey B's datasets are listed

#### Scenario: Counts follow the session scope
- **WHEN** a survey has 4 answered sessions, one of them trashed
- **THEN** its responses dataset shows 3 rows

### Requirement: The catalogue is reachable and filterable
The app sidebar SHALL carry a **Data** item that opens the catalogue. The catalogue SHALL filter
by source and privacy class and search by name through the address (so a filtered view is a
link), and each row SHALL link to where the data is edited or read today.

#### Scenario: Filter by source
- **WHEN** a member opens `/editor/data/?kind=answers`
- **THEN** only answers datasets are listed and the "Answers" filter is shown as active

#### Scenario: Sidebar item
- **WHEN** a member opens any editor page
- **THEN** the sidebar shows a Data item linking to the catalogue
