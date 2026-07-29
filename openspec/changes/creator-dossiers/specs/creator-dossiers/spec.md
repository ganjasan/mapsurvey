## ADDED Requirements

### Requirement: Structured creator profile

The system SHALL store at most one profile per registered user, holding
organisation, role, country, LinkedIn URL, website, how they found us, and a
markdown summary. All fields SHALL be optional, and an absent profile SHALL mean
"nothing recorded yet" rather than an error at any consumer.

#### Scenario: Profile is unique per user

- **WHEN** a second profile is created for a user who already has one
- **THEN** the write fails.

#### Scenario: Consumers tolerate a missing profile

- **GIVEN** a user with no profile
- **WHEN** the admin user page and the export are rendered
- **THEN** both succeed and show the profile fields as empty.

### Requirement: Append-only note timeline

The system SHALL store any number of dated notes per user, each with an author,
a kind from a fixed vocabulary (`research`, `email`, `call`, `signal`), a
markdown body and an optional source path. Notes SHALL be ordered newest first
when listed, and automated tooling SHALL only create notes, never update or
delete existing ones.

#### Scenario: Notes list newest first

- **GIVEN** a user with notes dated 2026-03-01 and 2026-07-01
- **WHEN** their notes are listed
- **THEN** the 2026-07-01 note comes first.

#### Scenario: Deleting a user removes their notes

- **WHEN** a user is deleted
- **THEN** their profile and notes are deleted with them.

#### Scenario: Author may be absent

- **GIVEN** a note whose author account is later deleted
- **WHEN** the note is read
- **THEN** the note still exists with no author.

### Requirement: Import of existing markdown dossiers

The system SHALL provide a command that imports a directory tree of
`<username>/profile.md` plus `<username>/correspondence/*.md` files. It SHALL
match each directory to a user by name first (case-insensitive, tolerating `_`
for `.` and a leading `@`) and, failing that, by an email address found in the
dossier header. It SHALL read labelled header fields into profile columns, store
the dossier body as a `research` note, and store each correspondence file as an
`email` note dated from its filename prefix. The command SHALL default to a dry
run, SHALL never modify the source files, and SHALL report directories that
match no user instead of guessing.

#### Scenario: Directory name differing only in punctuation still matches

- **GIVEN** a user named `sample.w266` and a dossier directory `sample_w266`
- **WHEN** the import runs
- **THEN** the dossier is attached to that user.

#### Scenario: Email in the header matches when the name does not

- **GIVEN** a user whose username is their email address and a dossier directory
  named differently, whose header carries that email
- **WHEN** the import runs
- **THEN** the dossier is attached to that user.

#### Scenario: Dossier body is preserved as a note

- **WHEN** a dossier is imported for a matching user
- **THEN** a `research` note exists for that user whose body contains the
  dossier text.

#### Scenario: Header fields populate the profile

- **GIVEN** a dossier with `Organization`, `Role` and `Location` header lines
- **WHEN** it is imported
- **THEN** the user's profile carries those values.

#### Scenario: Correspondence becomes dated email notes

- **GIVEN** a correspondence file named `2026-04-28_initial-outreach.md`
- **WHEN** it is imported
- **THEN** an `email` note exists dated 2026-04-28 whose body contains the file's
  text.

#### Scenario: Unmatched directory is reported, not imported

- **GIVEN** a dossier directory whose name matches no user
- **WHEN** the import runs
- **THEN** nothing is created for it and the directory is reported.

#### Scenario: Dry run writes nothing

- **WHEN** the command runs without the apply flag
- **THEN** no profile or note is created and the source files are unchanged.

#### Scenario: Re-import does not duplicate notes

- **GIVEN** an import has already been applied
- **WHEN** it is applied again over the same tree
- **THEN** no additional note is created for any file already imported.

#### Scenario: Re-import does not blank corrected fields

- **GIVEN** a profile whose organisation was corrected by hand and a dossier with
  no organisation header
- **WHEN** the import is applied again
- **THEN** the corrected organisation is retained.

#### Scenario: Tier is not imported

- **GIVEN** a dossier carrying a `Tier` header
- **WHEN** it is imported
- **THEN** no tier value is stored on the profile.

### Requirement: Staff access to profiles and notes

The system SHALL expose the profile and the note timeline on the user's page in
the Django admin, alongside cohorts, and SHALL restrict all access to staff.
Profiles and notes SHALL never be exposed to the user they describe or to any
public view.

#### Scenario: Staff sees profile and notes on the user page

- **WHEN** a staff member opens a user in the admin
- **THEN** the profile fields and that user's notes are shown.

#### Scenario: Non-staff cannot reach the records

- **WHEN** a user who is not staff requests a profile or note admin URL
- **THEN** access is denied.

### Requirement: Export for CRM migration and subject access

The system SHALL provide a command that exports profiles and notes as CSV: one
row per creator with the structured fields, and one row per note with username,
date, kind, author and body. The export SHALL be restrictable to a single user so
that it can answer a data subject access request.

#### Scenario: Export produces both files

- **WHEN** the export command runs
- **THEN** a profiles file and a notes file are written, with a header row each.

#### Scenario: Export for one user contains only that user

- **WHEN** the export is restricted to a single username
- **THEN** the output contains that user's rows and no other user's rows.

#### Scenario: Note bodies survive the round trip

- **GIVEN** a note whose body contains commas, quotes and newlines
- **WHEN** it is exported and the CSV is parsed again
- **THEN** the body matches the original.
