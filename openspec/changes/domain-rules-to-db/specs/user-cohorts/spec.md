## ADDED Requirements

### Requirement: Domain-to-segment rules live in the database

The system SHALL store domain-to-cohort mappings as staff-editable records, each
holding a unique lowercased email domain, the cohort it maps to and an optional
note. The source code SHALL NOT contain any mapping that names a specific
organisation; only generic rules (freemail providers, student-subdomain markers,
TLD suffixes) may remain in code.

#### Scenario: Domain is stored lowercased

- **WHEN** a rule is saved with a mixed-case domain
- **THEN** the stored domain is lowercase.

#### Scenario: One rule per domain

- **WHEN** a second rule is created for a domain that already has one
- **THEN** the write fails.

### Requirement: Classification consults the database rules first

`classify_segment` SHALL propose the cohort of a matching database rule before
applying any suffix rule, SHALL fall back to the generic rules when no database
rule matches, and SHALL still propose nothing for freemail or malformed
addresses. It SHALL accept a preloaded domain map so that bulk classification
does not query per user.

#### Scenario: Database rule wins over the suffix rule

- **GIVEN** a rule mapping an `.org` domain to the municipality cohort
- **WHEN** an address at that domain is classified
- **THEN** the municipality cohort is proposed, not the NGO cohort the `.org`
  suffix rule would give.

#### Scenario: Suffix rules still apply without any database rule

- **GIVEN** no database rules at all
- **WHEN** an `.ac.uk` address is classified
- **THEN** the university cohort is proposed.

#### Scenario: Freemail still yields nothing

- **GIVEN** a database rule exists for some other domain
- **WHEN** a `gmail.com` address is classified
- **THEN** nothing is proposed.

#### Scenario: Preloaded map is used instead of querying

- **GIVEN** a preloaded map mapping a domain to a cohort
- **WHEN** an address at that domain is classified with that map supplied
- **THEN** the mapped cohort is proposed even though no such rule exists in the
  database.

### Requirement: Domain rules are loadable from a local file

The system SHALL accept a `domain,cohort,note` file and upsert domain rules from
it, so the production rule set is reproducible without being committed to the
repository. Rows naming an unknown cohort SHALL be reported and skipped.

#### Scenario: Rules are created and updated from the file

- **GIVEN** a file naming a domain and a cohort
- **WHEN** it is applied twice, the second time with a different cohort
- **THEN** one rule exists for that domain, pointing at the cohort from the
  second run.

#### Scenario: Unknown cohort in the file is skipped

- **GIVEN** a file row naming a cohort slug that does not exist
- **WHEN** it is applied
- **THEN** that row is reported and no rule is created for it.

#### Scenario: Dry run writes no rules

- **WHEN** the rules file is loaded without the apply flag
- **THEN** no rule is created.
