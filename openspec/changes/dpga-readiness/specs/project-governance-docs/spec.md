## ADDED Requirements

### Requirement: README states license and ownership

`README.md` SHALL contain a section headed "License & ownership" that names the copyright holder as "Copyright © 2021–2026 Artem Koniukhov (sole proprietor, Kyrgyz Republic)", states the AGPLv3 license with a link to `LICENSE`, says contributions are accepted under the same license, says the Mapsurvey name identifies the project and the hosted service without claiming a registered trademark, and says collected data belongs to the survey creator. The README "Documentation" link SHALL point to `docs/OVERVIEW.md`, and the README SHALL link `CODE_OF_CONDUCT.md`.

#### Scenario: Ownership section and working documentation link

- **WHEN** `README.md` is read
- **THEN** it SHALL contain the heading "License & ownership" and the text "Artem Koniukhov"
- **AND** it SHALL NOT link to `mapsurvey.org/docs`
- **AND** it SHALL link to `docs/OVERVIEW.md` and `CODE_OF_CONDUCT.md`

### Requirement: Functional overview document

`docs/OVERVIEW.md` SHALL describe, for a reader unfamiliar with the project: what Mapsurvey is; the user groups already using it (municipalities and public agencies, community and neighbourhood councils, universities and students, planning and design consultancies, NGOs, citizen-science projects, educators); main functions for creators, respondents and results; the architecture (Django + GeoDjango, PostgreSQL/PostGIS, Redis, Celery, object storage); how to run it with Docker; which external services are optional and how they are switched; data formats; and project ownership, license, security and conduct links.

#### Scenario: Overview is self-contained

- **WHEN** `docs/OVERVIEW.md` is read
- **THEN** it SHALL contain a Docker quick start, the list of user groups, and the list of optional external services with their environment variables

### Requirement: Code of conduct

`CODE_OF_CONDUCT.md` SHALL contain the Contributor Covenant 2.1 with enforcement contact `konuchovartem@mapsurvey.org`, followed by a section "Using the hosted service" that points to `https://mapsurvey.org/terms/#acceptable-use` for conduct on mapsurvey.org.

#### Scenario: Code of conduct present

- **WHEN** `CODE_OF_CONDUCT.md` is read
- **THEN** it SHALL name Contributor Covenant version 2.1, contain `konuchovartem@mapsurvey.org`, and link `/terms/#acceptable-use`
