# survey-serialization Delta Specification

## ADDED Requirements

### Requirement: Visibility rules survive export and import

`survey.json` SHALL include each question's and section's `visibility_rule` (the
controlling question's code plus referenced option codes, or null). Import SHALL
resolve the controlling question through the same code remapping applied to question
codes, preserving option codes. A rule whose controlling question or all referenced
option codes cannot be resolved in the archive SHALL be dropped with a line in the
import report — never imported as a broken half-rule and never failing the import.

#### Scenario: Round-trip preserves a rule

- **GIVEN** a survey where section "Area 1 count" is shown when Area = code 1
- **WHEN** the survey is exported to ZIP and imported into a new survey
- **THEN** the imported section carries an equivalent rule referencing the remapped
  controlling question and option code 1

#### Scenario: Unresolvable rule is dropped and reported

- **GIVEN** an archive whose rule references a question code absent from the archive
- **WHEN** the archive is imported
- **THEN** the item imports without a rule
- **AND** the import report notes the dropped rule

#### Scenario: Archives without rules import unchanged

- **WHEN** an archive produced before this capability is imported
- **THEN** every question and section imports with no visibility rule
