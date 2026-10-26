## ADDED Requirements

### Requirement: Creators duplicate a whole survey
The dashboard's ⋯ menu SHALL offer "Duplicate" on every survey to workspace members who may create
surveys. It SHALL create the copy described for `POST /surveys/{uuid}/duplicate` through the same
service and open the copy's Build page. The source survey SHALL be unchanged whatever its status.

#### Scenario: Duplicate from the dashboard
- **WHEN** a workspace editor chooses Duplicate on a closed survey named "Benches 2026"
- **THEN** the editor opens a new draft survey "Benches 2026 (copy)" with the same sections, questions and layers and no responses

#### Scenario: Viewer sees no Duplicate
- **WHEN** a workspace viewer opens the ⋯ menu
- **THEN** there is no Duplicate item

### Requirement: Creators move a question to another section
Each top-level question row SHALL offer "Move to section…", listing the survey's other sections.
Choosing one SHALL move the question to the end of that section, with its sub-questions and answers,
through the move service. The question SHALL leave its group. A toast SHALL name every visibility
rule the move cleared. On a live survey the control SHALL open the structure gate instead.

#### Scenario: Move a question to the next section
- **WHEN** a creator chooses "Move to section… → Section 2" on a question of Section 1 in a draft survey
- **THEN** the question is the last question of Section 2 and no longer listed under Section 1

#### Scenario: Live survey
- **WHEN** the survey is published and has no unpublished changes
- **THEN** the control opens the "Change the structure of a live survey" gate

### Requirement: Copies into another survey own their files
Pasting a question or section into another survey, and duplicating a survey, SHALL store a new copy
of every cover image, question image and layer attachment under a new key. Purging either survey
from the trash SHALL never delete a file the other uses. Copies within one survey and its versions
MAY share files, because they are purged together.

#### Scenario: Purge the source after a paste
- **WHEN** a question with an image is pasted from survey A into survey B and A is purged from the trash
- **THEN** B's question image still loads
