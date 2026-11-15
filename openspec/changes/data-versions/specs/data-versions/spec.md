## ADDED Requirements

### Requirement: A new version is previewed before it is saved
The system SHALL let an editor of a layer dataset upload a new version of it. The file SHALL be
matched to the dataset's objects by the layer's key field, and the system SHALL show the number of
objects that would be added, changed, removed and left unchanged, and the number of answers on the
objects that would be removed, before changing anything.

#### Scenario: The preview counts
- **WHEN** a dataset of trees T1, T2, T3 receives a file with T1 changed, T2 unchanged and T4 new
- **THEN** the preview reads 1 added, 1 changed, 1 removed, 1 unchanged and the dataset is still T1, T2, T3 as before

#### Scenario: A dataset without a key field
- **WHEN** a new version is uploaded for a dataset whose layer has no key field
- **THEN** the job fails with a message asking for a key column

### Requirement: Applying a version updates objects in place
On the editor's confirmation with a change note, the system SHALL update matched objects in place,
add the new ones and remove the missing ones, so that answers about an object whose key is unchanged
stay attached to it, and every survey and Site that uses the dataset shows the new version.

#### Scenario: Answers survive
- **WHEN** a respondent's answer is attached to tree T1 and a version changing T1's height is applied
- **THEN** the answer is still attached to T1 and T1 carries the new height

#### Scenario: Every consumer shows the new version
- **WHEN** the dataset is linked into a survey and a version is applied
- **THEN** the survey's layer GeoJSON carries the new objects

#### Scenario: Above a survey map's limit while linked
- **WHEN** the dataset is linked into a survey and the new version has more than 5,000 objects
- **THEN** the job fails naming the limit and the dataset is unchanged

### Requirement: Versions have a history
The system SHALL record each applied version with its number, date, author, note and counts, and
SHALL list them on the dataset page.

#### Scenario: The history
- **WHEN** a version is applied with the note "Spring 2027 inspection"
- **THEN** the dataset page lists version 2 with that note and its author
