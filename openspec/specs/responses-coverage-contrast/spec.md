# responses-coverage-contrast Specification

## Purpose
TBD - created by archiving change coverage-contrast. Update Purpose after archive.
## Requirements
### Requirement: Coverage counts respondents, not shapes

A coverage surface SHALL count each respondent at most once per cell, however many shapes that
respondent drew for the source question, and the "of M respondents" figure SHALL be the number of
distinct respondents in scope.

#### Scenario: Two overlapping shapes from one person
- **WHEN** one respondent drew two overlapping polygons and another respondent drew one polygon
  over the same spot
- **THEN** the cell under all three shapes counts 2 and the row reads "≤ 2 of 2 respondents"

### Requirement: Coverage opacity scales to the strongest cell in view

A coverage surface SHALL draw the cell with the highest count in view at full opacity and the
lowest drawn count at the minimum opacity, interpolating between them. When every drawn cell has
the same count the surface SHALL be flat at the minimum opacity. Spray agreement surfaces SHALL
keep opacity by the absolute share of respondents.

#### Scenario: Moderate agreement is still visible
- **WHEN** 21 respondents are in scope and the strongest cell in view is covered by 12 of them
- **THEN** that cell is drawn at full opacity and a cell covered by one respondent at the minimum

#### Scenario: Spray unchanged
- **WHEN** a spray question's agreement surface is drawn
- **THEN** a cell's opacity is the minimum plus the range times its share of respondents in scope

### Requirement: The creator shapes the opacity curve

The coverage settings popover SHALL offer a Contrast control and a Minimum respondents control,
and SHALL show a preview of opacity against respondent count for the current settings. Contrast
SHALL bend the curve between its fixed ends: higher values keep low counts faint until near the
strongest cell, lower values raise low counts toward full colour. Minimum respondents SHALL hide
cells covered by fewer respondents and SHALL range from 1 to the respondents in scope. Changes
SHALL redraw the surface immediately and SHALL last as long as the slot.

#### Scenario: Raising contrast
- **WHEN** the creator moves Contrast to the right
- **THEN** cells with low counts get fainter, the strongest cell stays at full opacity, and the
  preview curve bends down

#### Scenario: Noise floor
- **WHEN** the creator sets Minimum respondents to 3
- **THEN** cells covered by one or two respondents are not drawn and a cell covered by three is
  the faintest drawn cell

