## MODIFIED Requirements

### Requirement: Story model
The system SHALL have a `Story` model with: `title` (CharField), `slug` (SlugField, unique),
`body` (TextField, HTML content), `cover_image` (ImageField, optional), `story_type` (CharField
with choices: `"map"`, `"open-data"`, `"results"`, `"article"`, `"case-study"`), `survey` (FK to
SurveyHeader, nullable), `is_published` (BooleanField, default False), `published_date`
(DateTimeField), the showcase fields `place`, `sector`, `summary`, `credit`, `credit_note`
(CharFields/TextField, blank), `credit_logo` and `card_image` (ImageFields, optional),
`cover_alt`, `cover_credit` (CharFields, blank), `facts` (JSONField, a list of
`{"value", "label"}` objects, default empty) and `topics` (JSONField, a list of topic slugs from
the registry in `survey/topics.py`, default empty).

#### Scenario: Create a story in admin
- **WHEN** an admin creates a Story with title, slug, body, story_type, and sets is_published to True
- **THEN** the story SHALL be persisted and queryable

#### Scenario: Story without survey link
- **WHEN** a Story is created without setting the survey FK
- **THEN** the story SHALL be valid with survey as NULL

#### Scenario: Story with survey link
- **WHEN** a Story is created with a FK to a SurveyHeader
- **THEN** the story SHALL reference that survey

#### Scenario: Slug uniqueness
- **WHEN** a Story is created with a slug that already exists
- **THEN** the system SHALL reject the creation with a uniqueness error

#### Scenario: Showcase fields are optional
- **WHEN** a Story is created with only title, slug and story_type
- **THEN** it SHALL be valid, with empty showcase fields, `facts == []` and `topics == []`

#### Scenario: Topics are validated
- **WHEN** a Story is saved from the admin with a topic slug that is not in the registry
- **THEN** the form SHALL reject it naming the slug
