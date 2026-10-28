## MODIFIED Requirements

### Requirement: Duplication carries the rule within a survey

Duplicating a question or a section SHALL copy its visibility rule verbatim. Creating a draft copy
or restoring an archived version SHALL copy every question and section rule verbatim (codes are
preserved, so the controller resolves in the copy). Pasting a copied item into a different survey
SHALL drop the rule (its controller does not exist there).

#### Scenario: Duplicated section keeps its rule

- **WHEN** the creator duplicates section "Area 1 count" (rule: Area = Area 1)
- **THEN** the copy carries the same rule, ready for re-ticking a different option

#### Scenario: Draft copy keeps the rules

- **WHEN** the creator starts unpublished changes on a survey with conditional questions and sections
- **THEN** the draft carries every rule, and publishing it keeps them on the live survey

#### Scenario: Cross-survey paste drops the rule

- **WHEN** a copied conditioned question is pasted into another survey
- **THEN** the pasted question has no visibility rule
