# render-deployment — delta for python312-django52-upgrade

## ADDED Requirements

### Requirement: Runtime versions are supported upstream
The Docker image SHALL run a CPython release inside its upstream security-support window
and a Django LTS release inside its extended-support window, and both SHALL be pinned
explicitly (`Dockerfile` base image; `Pipfile` `python_version` and a `~=` Django pin) so
that dependency resolution cannot re-pin an end-of-life Django silently. The lock file
SHALL be generated under the same Python the image runs.

#### Scenario: Image runs supported versions
- **WHEN** the production image is built from the Blueprint
- **THEN** it runs Python 3.12 and Django 5.2 LTS

#### Scenario: Resolver cannot drift to an unsupported Django
- **WHEN** `pipenv lock` is run
- **THEN** the resolved Django stays within the pinned LTS series regardless of what newer major versions exist

#### Scenario: Respondent pages render unchanged after the upgrade
- **WHEN** a section page of a published survey is rendered
- **THEN** its form markup (one table row per field, the project's widget templates) is the same structure as before the upgrade
