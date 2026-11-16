## ADDED Requirements

### Requirement: The grid counts marks as well as respondents
The grid SHALL report, for every cell it shows, the number of marks inside it: each point, and each
dot of a spray cloud, that falls in the cell. A line or polygon SHALL count as one mark in every
cell it touches. Whether a cell is shown SHALL still depend only on its number of distinct
respondents.

#### Scenario: Two points from one respondent
- **WHEN** 3 respondents placed points in one cell, one of them two points, and K = 3
- **THEN** the cell reports 3 respondents and 4 marks

#### Scenario: Marks do not unlock a cell
- **WHEN** 2 respondents placed 10 points in one cell and K = 3
- **THEN** the cell is omitted
