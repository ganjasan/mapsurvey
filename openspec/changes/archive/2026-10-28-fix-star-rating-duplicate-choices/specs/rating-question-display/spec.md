## ADDED Requirements

### Requirement: Opening a star question keeps its choices

Opening an existing rating question with the stars style in the editor SHALL show exactly the choices
the question has. The five default steps SHALL be added only when the question has no choices, and
only once. Choice codes within one question SHALL be unique: a save whose choice list repeats a code
SHALL be refused at the choices stage with a message naming the repeated code, and nothing SHALL be
stored.

#### Scenario: Existing stars question opens with its own five choices

- **WHEN** a creator opens a stars question whose five choices are "Unsafe" … "Very Safe"
- **THEN** the choices table holds those five rows and no others, and the star count reads 5

#### Scenario: New stars question gets five steps

- **WHEN** a creator picks the stars style on a rating question with no choices
- **THEN** the choices table holds five rows numbered 1–5

#### Scenario: Duplicate codes are refused

- **WHEN** a save posts a choice list in which code 1 appears twice
- **THEN** the save fails at the choices stage naming code 1, and the stored choices are unchanged
