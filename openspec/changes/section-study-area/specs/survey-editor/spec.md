## ADDED Requirements

### Requirement: The survey's study area is set in Survey settings
Survey settings → Respondent map SHALL show the survey's study area next to the default position:
its summary (place, size, fog, refusal), Set or Edit (the study area editor), Remove (through the
editor's confirmation dialog), and switches for fog and for refusing map answers outside, saved at
once. The message SHALL stay in the study area editor. The controls SHALL be available to the
editor role and above and SHALL apply in place on a published survey.

#### Scenario: Set from Survey settings
- **WHEN** a creator opens Survey settings on a survey with no study area
- **THEN** the Respondent map card offers Set, which opens the study area editor, whose Back returns to the survey

#### Scenario: Fog switched off in Survey settings
- **WHEN** the creator switches fog off in the Respondent map card
- **THEN** the survey's area keeps its outline with fog off, without leaving Survey settings

### Requirement: The Map card chooses the section's area
A map section's Map card SHALL offer three choices for its area: Survey's area (default, with a
read-only summary of the survey's area or a pointer to Survey settings when there is none), Own area
(with its summary and Edit, opening the study area editor for that section), and No area. A choice
SHALL save at once. Choosing Own area for a section without an outline SHALL open the editor for the
section, starting from the survey's outline when there is one, and nothing SHALL be stored until
Save. The study area editor for a section SHALL name the section, save the outline and rules for the
section only, and its Remove SHALL return the section to the survey's area.

#### Scenario: Own area from the Map card
- **WHEN** a creator picks Own area on a section that never had one and saves an outline in the editor
- **THEN** the Map card shows Own area with that outline's size, and the survey's area is unchanged

#### Scenario: No area from the Map card
- **WHEN** a creator picks No area
- **THEN** the choice saves at once and the Live preview shows no outline on that section
