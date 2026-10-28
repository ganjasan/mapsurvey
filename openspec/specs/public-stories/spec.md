# Public Stories Specification

## Purpose
The customer-story content type behind `/stories/` — the Story model and its admin, the cards on the landing page, and the detail page with its own base template.
## Requirements
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

### Requirement: Story admin registration
The Story model SHALL be registered in Django admin for content management.

#### Scenario: Admin can manage stories
- **WHEN** an admin user navigates to `/admin/survey/story/`
- **THEN** they SHALL see a list of all stories with title, story_type, is_published, and published_date columns

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

### Requirement: Story detail base template
The story detail page SHALL use `base_landing.html` as its base template, maintaining the same visual identity as the landing page.

#### Scenario: Consistent navigation
- **WHEN** a user views a story detail page
- **THEN** the page SHALL have the same navbar and footer as the landing page

### Requirement: Story type labels
Story types SHALL be displayed with human-readable labels: `"map"` → "Map", `"open-data"` →
"Open Data", `"results"` → "Results", `"article"` → "Article", `"case-study"` → "Case study".

#### Scenario: Type badge display
- **WHEN** a story of type `"open-data"` is displayed
- **THEN** its type badge SHALL read "Open Data"

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

A story SHALL be installed or refreshed from `survey/story_data/<slug>/` by `seed_story <slug>`.
A story installed for the first time SHALL be unpublished unless `--publish` is given. A re-run
SHALL keep the story's publication state unless `--publish` or `--draft` is given. A re-run SHALL
keep the row, its id and its `published_date`.

#### Scenario: Prepared story goes to production as a draft
- **WHEN** `seed_story <slug>` runs on a database without that story
- **THEN** the story exists, is unpublished, and is absent from the landing, `/stories/` and the sitemap

A story MAY be read from a directory outside the repository (`--from DIR`), so that text and
pictures a customer has not approved never reach the public repository.

#### Scenario: Refresh keeps a published story published
- **WHEN** `seed_story <slug>` runs again for a published story
- **THEN** it stays published with the same id and date

### Requirement: Story pictures open in a lightbox
On the story detail page every picture of the story (cover and body figures) SHALL open, on
click, in a lightbox showing the picture at up to viewport size with its caption (the figure's
caption, else the alt text), a position counter, previous/next controls that wrap within the
story, and a close control. The lightbox SHALL close on the close control, on Escape and on a
click outside the picture; the arrow keys SHALL step between pictures. The credit logo is not a
story picture.

#### Scenario: Open and read the caption
- **WHEN** a visitor clicks the route-map figure in a story
- **THEN** the lightbox shows that image with the figure's caption and a counter such as "3 / 12"

#### Scenario: Step to the next picture
- **WHEN** the lightbox is open and the visitor presses the next control or the right arrow key
- **THEN** the lightbox shows the following picture of the same story, wrapping to the first
  after the last

#### Scenario: Close
- **WHEN** the visitor presses Escape, the close control, or clicks the backdrop
- **THEN** the lightbox closes and focus returns to the picture that opened it

#### Scenario: Story without pictures
- **WHEN** a story with no pictures is rendered
- **THEN** the page renders normally and the lightbox is never shown

### Requirement: Story callouts are readable in both colour schemes
The Lessons learned callout and the draft banner on a story page SHALL set their own text colour
together with their surface, and SHALL provide a dark variant under `prefers-color-scheme: dark`,
so that no text in them inherits a theme colour drawn against a fixed surface. Every text/surface
pair SHALL meet WCAG AA contrast (4.5:1) in both schemes. In the dark scheme the Lessons learned
callout SHALL stand out from the page as it does in the light scheme — a warm surface lighter than
the page background and an accent outline — rather than blend into the page.

#### Scenario: Dark-mode phone reads the lessons
- **WHEN** a visitor whose device uses the dark colour scheme opens a story with a Lessons learned callout
- **THEN** the callout renders on a warm surface clearly lighter than the page, outlined in the accent colour, with light text, and its headings, paragraphs and "In Mapsurvey" lines are legible

#### Scenario: Light mode unchanged
- **WHEN** a visitor in the light colour scheme opens the same story
- **THEN** the callout looks as before (warm light surface, dark text)

### Requirement: Stories index page
The system SHALL serve a public stories index at `/stories/` that lists all published stories as a card grid, ordered by `published_date` descending (unpublished stories excluded). The page SHALL return HTTP 200 even when no stories are published.

#### Scenario: Index lists published stories
- **WHEN** an anonymous visitor requests `/stories/` and published stories exist
- **THEN** the response status SHALL be 200
- **AND** each published story's title SHALL appear with a link to its `stories/<slug>/` detail page

#### Scenario: Draft stories excluded
- **WHEN** `/stories/` is requested and a story has `is_published=False`
- **THEN** that story's title and slug SHALL NOT appear in the response

#### Scenario: Empty state
- **WHEN** `/stories/` is requested and no stories are published
- **THEN** the response status SHALL be 200
- **AND** the page SHALL show an empty-state message rather than an error

### Requirement: Stories index structured data
The stories index SHALL emit a `BreadcrumbList` JSON-LD (`Home › Stories`) and a `CollectionPage` JSON-LD whose `mainEntity` is an `ItemList` of the listed stories.

#### Scenario: Breadcrumb and collection present and valid
- **WHEN** `/stories/` is requested with at least one published story
- **THEN** the HTML SHALL contain a `<script type="application/ld+json">` with `"@type": "BreadcrumbList"` (Home then Stories)
- **AND** a `<script type="application/ld+json">` with `"@type": "CollectionPage"` whose `ItemList` has one entry per listed story
- **AND** every JSON-LD script SHALL parse as valid JSON

### Requirement: Story detail SEO metadata
Each published story detail page SHALL provide a self-referencing `canonical` URL, a `meta_description` derived from the story, and a `BreadcrumbList` JSON-LD (`Home › Stories › <title>`).

#### Scenario: Detail page canonical and breadcrumb
- **WHEN** a published story at `stories/<slug>/` is requested
- **THEN** the HTML SHALL contain a `<link rel="canonical">` whose href ends with `/stories/<slug>/`
- **AND** a `BreadcrumbList` JSON-LD with three ordered items: Home, Stories, and the story title
- **AND** a non-empty `<meta name="description">`

### Requirement: Stories in sitemap
`sitemap.xml` SHALL include the `/stories/` hub and one entry per published story. Unpublished stories SHALL NOT appear.

#### Scenario: Hub and published stories listed
- **WHEN** `/sitemap.xml` is requested and a published story exists
- **THEN** the sitemap SHALL contain a `<loc>` for `/stories/`
- **AND** a `<loc>` for that story's `stories/<slug>/` URL

#### Scenario: Draft story not in sitemap
- **WHEN** `/sitemap.xml` is requested and a story is unpublished
- **THEN** the sitemap SHALL NOT contain that story's `stories/<slug>/` URL

### Requirement: Stories link in landing footer
The landing footer SHALL link to the stories index at `/stories/`.

#### Scenario: Footer links to stories
- **WHEN** any page extending `base_landing.html` is rendered
- **THEN** the footer SHALL contain a link with href `/stories/`

### Requirement: Showcase order set by staff

Published stories SHALL be listed on the landing carousel and on `/stories/` by the `position`
staff set in the admin, lowest first; stories without a position SHALL follow, newest first.
Re-installing a story with `seed_story` SHALL NOT change its position.

#### Scenario: Owner puts three stories first
- **WHEN** staff give Olney position 1, Whitehouse 2 and Remington 3
- **THEN** the carousel and `/stories/` start with Olney, Whitehouse, Remington, followed by the other published stories newest first

### Requirement: Publishing from the admin

Staff SHALL publish and unpublish stories from the Django admin: the list's publication
checkbox and the "Publish" / "Unpublish" actions. Publishing SHALL set `published_date` when it
is empty.

#### Scenario: Publish after the customer's OK
- **WHEN** staff run "Publish" on a draft story
- **THEN** it is published, dated, and appears on the landing and `/stories/`

### Requirement: Staff preview of a draft

An unpublished story SHALL return 404 to everyone except staff. Staff SHALL see it at its normal
URL with a "Draft — not public" banner and a `noindex` robots meta.

#### Scenario: Owner checks a draft on production
- **WHEN** a staff user opens `/stories/<slug>/` of an unpublished story
- **THEN** the page renders with the draft banner and noindex

#### Scenario: Visitor tries a draft URL
- **WHEN** an anonymous visitor opens it
- **THEN** the response is 404

### Requirement: Lessons learned callout

A story body MAY contain one "Lessons learned" callout (`<aside class="sd-lessons">`). The callout SHALL look the same in every story: the lessons-learned mark, the heading "Lessons learned", and numbered lessons. Each lesson MAY end with an "In Mapsurvey" line naming what the product offers for it, tagged Available, Built for <customer>, or Not yet; a Not yet line SHALL use the dashed mark so a gap is never presented as a feature.

#### Scenario: Story with lessons
- **WHEN** a story body contains the callout
- **THEN** the story page renders it with the mark, numbered lessons and their In Mapsurvey lines

### Requirement: Lessons badge on the story card

A story card SHALL show a "Lessons learned" badge on its cover when the story body contains the
callout, and SHALL NOT show it otherwise.

#### Scenario: Card of a story with lessons
- **WHEN** the landing or `/stories/` lists a published story whose body contains the callout
- **THEN** its card shows the "Lessons learned" badge

#### Scenario: Card of a story without lessons
- **WHEN** a listed story's body has no callout
- **THEN** its card shows no badge

