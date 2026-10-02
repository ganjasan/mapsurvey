# repo-hygiene — delta for ops-repo-separation

## ADDED Requirements

### Requirement: Operational material lives outside the public repository
Operational material SHALL live in the private ops repository, never in this public one:
outreach dossiers, customer stories, cohorts, GTM and business plans, competitor notes,
requirements, raw notes and legal drafts. Code SHALL locate that material only through `settings.OPS_DIR`, and
only tooling (management commands, tests) MAY read it; a test that needs it SHALL skip
when the directory is absent.

#### Scenario: Fresh clone without the ops repo
- **WHEN** the test suite runs in CI or on a fresh clone with no `../Mapsurvey-ops`
- **THEN** tests that read operational files skip and nothing else fails

#### Scenario: Ops path overridden
- **WHEN** `MAPSURVEY_OPS_DIR` is set
- **THEN** `settings.OPS_DIR` points there instead of `../Mapsurvey-ops`

### Requirement: People are pseudonymised in tracked files
Tracked specs, docs and agent instructions SHALL NOT contain a real person's email address;
people SHALL be referred to as `lead-NNN`, resolved only through the key in the ops repo.
Our own addresses, public mailing lists and obvious placeholders are allowed.

#### Scenario: A lead's address is pasted into a backlog item
- **WHEN** a tracked file under `openspec/`, `docs/` or `.claude/` contains a lead's real address
- **THEN** `RepoHygieneTest` fails and names the file and the address

#### Scenario: Placeholder addresses
- **WHEN** a spec quotes `x@example.org`, `a@gmail.com` or `info@mapsurvey.org`
- **THEN** `RepoHygieneTest` passes
