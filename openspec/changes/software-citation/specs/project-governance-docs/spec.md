## ADDED Requirements

### Requirement: Citation file

The repository root SHALL contain `CITATION.cff` in Citation File Format 1.2.0 with `cff-version`, `message`, `type: software`, `title: Mapsurvey`, one author with `family-names: Koniukhov` and `given-names: Artem` (the copyright holder named in the README), `license: AGPL-3.0-only`, `url: https://mapsurvey.org` and `repository-code: https://github.com/ganjasan/mapsurvey`. When a DOI is minted for the project, it SHALL be added as `doi`.

#### Scenario: Citation file is present and complete

- **WHEN** `CITATION.cff` is read
- **THEN** it SHALL contain `cff-version: 1.2.0`, `title: Mapsurvey`, `family-names: Koniukhov`, `license: AGPL-3.0-only` and the site and repository URLs
