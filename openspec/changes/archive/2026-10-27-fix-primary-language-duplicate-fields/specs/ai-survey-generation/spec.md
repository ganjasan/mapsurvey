# AI Survey Generation — delta


## MODIFIED Requirements

### Requirement: Multilingual generation in one call
The system SHALL produce content for all of the survey's `available_languages` in a
single provider call; materialization SHALL populate base fields from
the first (primary) language and create `SurveySectionTranslation`/`QuestionTranslation` rows
for every **non-primary** language only. No translation rows SHALL be created for the primary
language. Choice names SHALL be materialized as flat primary-language strings for
single-language surveys and as per-language dicts (primary key included) for multilingual
surveys — the same shapes the editor produces.

#### Scenario: Two-language survey
- **WHEN** a brief is generated with languages `["en", "it"]`
- **THEN** a single provider call is made, base fields are English, every section/question has
  an `it` translation row and no `en` translation row, and every choice name dict contains
  both `en` and `it` keys

#### Scenario: Single-language survey
- **WHEN** a brief is generated with languages `["es"]`
- **THEN** base fields carry the Spanish text, no translation rows are created, and choice
  names are flat strings

## ADDED Requirements

### Requirement: Prompt supports the self-registration pattern
The generation prompt SHALL instruct the model to recognize briefs where respondents map
something they own or represent (their business, project, home, or initiative) and to frame
such surveys in the first person about the respondent's own place, rather than defaulting to
an observer framing. Use-case guidance SHALL NOT hard-code a single respondent role: the
`citizen_science` guidance SHALL admit both observation and self-registration readings. The
prompt rules and `docs/research/survey-design-rules.md` SHALL be updated together.

#### Scenario: Inventory brief produces first-person framing
- **WHEN** a brief describes building a registry of local entrepreneurs and the audience is
  the people being mapped
- **THEN** the generated draft asks respondents to register and describe their own
  place/business (first person), with the geo question collecting the respondent's own
  location rather than third-party observations
