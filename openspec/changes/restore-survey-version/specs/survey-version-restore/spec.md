# survey-version-restore

## ADDED Requirements

### Requirement: Restore an archived version as a new draft
The system SHALL let a survey owner create a draft copy whose sections and questions
are cloned from a chosen archived version of the same survey family. Publishing that
draft MUST follow the standard draft workflow and produce a new version number —
history is append-only and no existing version or session is modified. The draft's
survey-level settings (name, languages, map defaults, thanks page) MUST come from the
current canonical; only the questionnaire structure comes from the archived version.

#### Scenario: Restore recreates the old questionnaire
- **GIVEN** v2 had question QDROP, which was removed in v3
- **WHEN** the owner restores v2 as a draft and publishes it
- **THEN** the new current version contains QDROP with its original code

#### Scenario: Restored lineage returns from the Archived group
- **GIVEN** QDROP's v1–v2 answers reported under "Archived questions" while v3 was
  current
- **WHEN** a restored draft containing QDROP is published
- **THEN** QDROP's lineage is current again and its historical answers report in the
  main analytics without an archived badge

#### Scenario: Restore is blocked while a draft exists
- **WHEN** the owner attempts to restore a version while the survey already has a
  draft copy
- **THEN** the request is rejected with a conflict and no draft is created

#### Scenario: Only family versions can be restored
- **WHEN** the requested version number does not match an archived member of the
  survey's family
- **THEN** the request fails with not-found and no draft is created

### Requirement: Version history with restore actions in the publishing widget
The publishing widget's Version section SHALL list the survey's archived versions and
offer a "Restore as draft" action per version to owners, only while the canonical is
published and has no active draft copy.

#### Scenario: Owner sees restore actions
- **WHEN** an owner opens the publishing widget of a published v3 survey with an
  archived v2 and no draft
- **THEN** a v2 row with a "Restore as draft" action is shown

#### Scenario: Hidden while a draft exists
- **WHEN** the survey already has a draft copy
- **THEN** no restore actions are rendered
