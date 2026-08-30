# organization-identity Specification (delta)

## ADDED Requirements

### Requirement: An organization slug is always routable
The system SHALL NOT persist an `Organization.slug` that cannot be reversed by the `org/<slug>/`
URL patterns. A slug written through any code path — the settings form, Django admin, a management
command, a shell session, an import — SHALL either match the routable character set or be
normalised to a value that does, preserving uniqueness across organizations.

#### Scenario: Human-readable text typed into the slug field is rejected with an error
- **WHEN** an organization owner submits the settings form with a slug containing spaces or punctuation outside the routable set
- **THEN** the organization is left unchanged, the settings page re-renders with a field error naming the allowed characters, and no page of the editor breaks

#### Scenario: A non-routable slug written outside the form is normalised
- **WHEN** code assigns a non-routable slug to an organization and saves it
- **THEN** the stored slug is a normalised, routable value, unique among organizations

#### Scenario: A valid slug is stored exactly as typed
- **WHEN** an owner submits a slug that already matches the routable set
- **THEN** it is stored verbatim, with no normalisation applied

#### Scenario: A duplicate slug is refused, not silently suffixed
- **WHEN** an owner submits a slug already held by another organization
- **THEN** the form re-renders with a uniqueness error and the organization keeps its current slug

### Requirement: Existing non-routable slugs are repaired
Organizations stored before this change whose slug does not match the URL pattern SHALL be
migrated to a routable slug derived from their name, keeping uniqueness. This restores editor
access for owners whose account dropdown currently raises `NoReverseMatch` on every page.

#### Scenario: A stored slug with spaces is repaired on migrate
- **WHEN** the migration runs against an organization whose slug contains spaces or an apostrophe
- **THEN** the slug becomes a routable, unique value and every editor page renders for that owner

#### Scenario: Already-routable slugs are untouched
- **WHEN** the migration runs against an organization whose slug is already routable
- **THEN** the slug is unchanged
