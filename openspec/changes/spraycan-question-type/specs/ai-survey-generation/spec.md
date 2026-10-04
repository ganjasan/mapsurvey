## ADDED Requirements

### Requirement: The model may draft a spraycan question for fuzzy areas

The generation prompt SHALL offer `spraycan` as an input type with guidance: use it when the
brief asks where something is felt, perceived or roughly extends without a boundary (safety,
heat, noise, "where the centre ends"); use `polygon` when the brief asks for a bounded area. The
validation gate SHALL accept `spraycan` as a geo type under the existing "at most one top-level
geo question" rule, and materialisation SHALL set `spray_brush = medium`. The create page's
example brief chips SHALL include one that naturally yields a spraycan question.

#### Scenario: Perception brief yields a spraycan question
- **WHEN** the brief reads "Where do residents feel unsafe after dark?"
- **THEN** a valid draft may contain a `spraycan` top-level question, and it materialises with
  brush size `medium`

#### Scenario: Spraycan counts as the one geo question
- **WHEN** the model returns a `spraycan` and a `point` top-level question in one draft
- **THEN** validation fails with the existing "at most one geo question" error and the retry
  carries it
