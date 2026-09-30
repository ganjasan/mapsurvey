## MODIFIED Requirements

### Requirement: Story model
The system SHALL have a `Story` model with: `title` (CharField), `slug` (SlugField, unique),
`body` (TextField, HTML content), `cover_image` (ImageField, optional), `story_type` (CharField
with choices: `"map"`, `"open-data"`, `"results"`, `"article"`, `"case-study"`), `survey` (FK to
SurveyHeader, nullable), `is_published` (BooleanField, default False), `published_date`
(DateTimeField), and the showcase fields `place`, `sector`, `summary`, `credit`, `credit_note`
(CharFields/TextField, blank), `credit_logo` and `card_image` (ImageFields, optional),
`cover_alt`, `cover_credit` (CharFields, blank) and `facts` (JSONField, a list of
`{"value", "label"}` objects, default empty).

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
- **THEN** it SHALL be valid, with empty showcase fields and `facts == []`

### Requirement: Stories section on landing page
The landing page SHALL display a "From the field" carousel of published stories between the
hero and the product showcase, newest first, with a link to `/stories/`.

#### Scenario: Published stories shown
- **WHEN** the landing page is rendered and there are published stories
- **THEN** the carousel SHALL contain one card per story where is_published is True, ordered by published_date descending

#### Scenario: No published stories
- **WHEN** the landing page is rendered and there are no published stories
- **THEN** the carousel section SHALL be omitted entirely

#### Scenario: Unpublished story
- **WHEN** a story has is_published False
- **THEN** it SHALL appear neither on the landing page nor on `/stories/`

### Requirement: Story card content
Each story card (landing carousel and `/stories/`) SHALL display the card image (`card_image`,
falling back to `cover_image`), the story type label, the place and sector, the title, the
summary, up to six fact chips, and the credit line with the credit logo when present.

#### Scenario: Story card with cover image
- **WHEN** a story card is rendered for a story with a card or cover image
- **THEN** the card SHALL display that image with the type label over it

#### Scenario: Story card without cover image
- **WHEN** a story card is rendered for a story without any image
- **THEN** the card SHALL display a placeholder background and the type label

#### Scenario: Story card links to detail
- **WHEN** a user clicks a story card
- **THEN** the system SHALL navigate to `/stories/<slug>/`

### Requirement: Story detail page
The system SHALL serve a story detail page at `/stories/<slug>/` showing the eyebrow (place ·
sector), title, summary as the lead, byline (credit, credit note, credit logo, type label and
published date), the cover with `cover_alt` and `cover_credit`, the fact strip, the body, and a
shared call-to-action to create a survey.

#### Scenario: View published story
- **WHEN** a user navigates to `/stories/<slug>/` for a published story
- **THEN** the system SHALL render the eyebrow, title, lead, byline, cover, facts and body

#### Scenario: View unpublished story
- **WHEN** a user navigates to `/stories/<slug>/` for an unpublished story
- **THEN** the system SHALL return a 404 response

#### Scenario: Non-existent story
- **WHEN** a user navigates to `/stories/<slug>/` with a slug that does not exist
- **THEN** the system SHALL return a 404 response

#### Scenario: Story linked to survey
- **WHEN** a story detail page is rendered for a story with a survey FK
- **THEN** the page SHALL display a link to the survey at `/surveys/<uuid>/`

### Requirement: Story type labels
Story types SHALL be displayed with human-readable labels: `"map"` → "Map", `"open-data"` →
"Open Data", `"results"` → "Results", `"article"` → "Article", `"case-study"` → "Case study".

#### Scenario: Type badge display
- **WHEN** a story of type `"open-data"` is displayed
- **THEN** its type badge SHALL read "Open Data"

## ADDED Requirements

### Requirement: Body images
A story SHALL own zero or more `StoryImage` rows (`key` unique within the story, `image` on the
public media tier). The body MAY reference them as `{img:<key>}`; the detail view SHALL replace
each token with the image's URL before rendering.

#### Scenario: Token resolved
- **WHEN** a story body contains `<img src="{img:route-zones}">` and the story has a StoryImage
  with key `route-zones`
- **THEN** the rendered page SHALL contain that image's storage URL in the `src`

#### Scenario: Unknown token
- **WHEN** a body references a key the story has no image for
- **THEN** the token SHALL render as an empty string and the page SHALL still return 200

### Requirement: Stories are installed from the repository
The system SHALL provide a management command `seed_story <slug>` that creates or updates the
story from `survey/story_data/<slug>/` (`story.json`, `body.html`, `images/`), uploading the
images to the public media tier and pointing the story's image fields and `StoryImage` rows at
them. The command SHALL be idempotent by slug.

#### Scenario: Fresh install
- **WHEN** `seed_story olney-white-squirrel-count` runs on a database without that slug
- **THEN** a published Story with that slug exists with its showcase fields, cover, card image,
  credit logo and every image listed in `story.json`

#### Scenario: Re-run updates in place
- **WHEN** the command runs again after `body.html` changed
- **THEN** the same row (same id and `published_date`) carries the new body

#### Scenario: Draft
- **WHEN** the command runs with `--draft`
- **THEN** the story is created or updated with `is_published` False

#### Scenario: Unknown slug
- **WHEN** the command is given a slug without a data directory
- **THEN** it SHALL fail with a `CommandError` and change nothing
