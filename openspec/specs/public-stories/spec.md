## ADDED Requirements

### Requirement: Story model
The system SHALL have a `Story` model with: `title` (CharField), `slug` (SlugField, unique), `body` (TextField, HTML content), `cover_image` (ImageField, optional), `story_type` (CharField with choices: `"map"`, `"open-data"`, `"results"`, `"article"`), `survey` (FK to SurveyHeader, nullable), `is_published` (BooleanField, default False), `published_date` (DateTimeField).

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

### Requirement: Story admin registration
The Story model SHALL be registered in Django admin for content management.

#### Scenario: Admin can manage stories
- **WHEN** an admin user navigates to `/admin/survey/story/`
- **THEN** they SHALL see a list of all stories with title, story_type, is_published, and published_date columns

### Requirement: Stories section on landing page
The landing page SHALL display a stories section with published stories.

#### Scenario: Published stories shown
- **WHEN** the landing page is rendered and there are published stories
- **THEN** the stories section SHALL display cards for stories where is_published is True, ordered by published_date descending

#### Scenario: No published stories
- **WHEN** the landing page is rendered and there are no published stories
- **THEN** the stories section SHALL be hidden entirely

### Requirement: Story card content
Each story card on the landing page SHALL display the title, story type label, cover image (if present), and published date.

#### Scenario: Story card with cover image
- **WHEN** a story card is rendered for a story with a cover_image
- **THEN** the card SHALL display the cover image, title, story type badge, and published date

#### Scenario: Story card without cover image
- **WHEN** a story card is rendered for a story without a cover_image
- **THEN** the card SHALL display a placeholder or solid-color background, title, story type badge, and published date

#### Scenario: Story card links to detail
- **WHEN** a user clicks a story card
- **THEN** the system SHALL navigate to `/stories/<slug>/`

### Requirement: Story detail page
The system SHALL serve a story detail page at `/stories/<slug>/`.

#### Scenario: View published story
- **WHEN** a user navigates to `/stories/<slug>/` for a published story
- **THEN** the system SHALL render the story title, published date, story type, body (as HTML), and cover image

#### Scenario: View unpublished story
- **WHEN** a user navigates to `/stories/<slug>/` for an unpublished story
- **THEN** the system SHALL return a 404 response

#### Scenario: Non-existent story
- **WHEN** a user navigates to `/stories/<slug>/` with a slug that does not exist
- **THEN** the system SHALL return a 404 response

#### Scenario: Story linked to survey
- **WHEN** a story detail page is rendered for a story with a survey FK
- **THEN** the page SHALL display a link to the survey at `/surveys/<name>/`

### Requirement: Story detail base template
The story detail page SHALL use `base_landing.html` as its base template, maintaining the same visual identity as the landing page.

#### Scenario: Consistent navigation
- **WHEN** a user views a story detail page
- **THEN** the page SHALL have the same navbar and footer as the landing page

### Requirement: Story type labels
Story types SHALL be displayed with human-readable labels: `"map"` → "Map", `"open-data"` → "Open Data", `"results"` → "Results", `"article"` → "Article".

#### Scenario: Type badge display
- **WHEN** a story of type `"open-data"` is displayed
- **THEN** its type badge SHALL read "Open Data"
