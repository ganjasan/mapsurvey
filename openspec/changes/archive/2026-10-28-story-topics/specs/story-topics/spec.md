## ADDED Requirements

### Requirement: Topic registry
The system SHALL keep the story topics in one registry, `survey/topics.py`, each with a slug, a label and optionally the key of the SEO landing page it belongs to. A landing key SHALL appear on at most one topic. `seed_story` SHALL refuse a `story.json` whose `topics` contain a slug that is not in the registry.

#### Scenario: Unknown topic in story.json
- **WHEN** `seed_story` reads a story whose `topics` list contains a slug absent from the registry
- **THEN** it fails with an error naming the slug and installs nothing

#### Scenario: Known topics are stored
- **WHEN** `seed_story` reads a story with `topics: ["community-engagement", "parks-public-space"]`
- **THEN** the Story row's `topics` equals that list in that order

### Requirement: Topic chips on the story page
The story detail page SHALL show the story's topics as chips under the eyebrow, in registry order of the story's list. A chip whose topic has a landing page SHALL link to that page; a chip whose topic has none SHALL be plain text.

#### Scenario: Topic with a landing page
- **WHEN** a published story tagged `community-engagement` is rendered
- **THEN** the page contains a chip "Community engagement" linking to `/community-engagement-platform/`

#### Scenario: Topic without a landing page
- **WHEN** a published story tagged `citizen-science` is rendered
- **THEN** the page contains the chip "Citizen science" with no link

#### Scenario: Story without topics
- **WHEN** a published story with `topics == []` is rendered
- **THEN** no chip row is rendered

### Requirement: Topic filter on the stories index
`/stories/` SHALL offer a filter row with one chip per topic that at least one published story carries, plus "All". `?topic=<slug>` SHALL limit the grid to the stories carrying that topic and mark the chip as active; an unknown slug SHALL show every story. The canonical URL and the CollectionPage structured data SHALL remain those of `/stories/` whatever the filter.

#### Scenario: Filtered index
- **WHEN** `/stories/?topic=parks-public-space` is requested and two of four published stories carry that topic
- **THEN** the grid shows those two, the "Parks and public space" chip is active, and the canonical link is `https://mapsurvey.org/stories/`

#### Scenario: Unknown topic
- **WHEN** `/stories/?topic=no-such-topic` is requested
- **THEN** every published story is shown

#### Scenario: Only used topics are offered
- **WHEN** no published story carries `citizen-science`
- **THEN** the filter row has no "Citizen science" chip

### Requirement: Stories on their topic's landing page
Every SEO landing page whose topic is set SHALL show a "From the field" block before the FAQ, listing the published stories carrying that topic, newest first in showcase order, rendered with the shared story card. The block SHALL be omitted when no published story carries the topic. Landing pages with no topic (the alternatives pages) SHALL render no block.

#### Scenario: Landing with matching stories
- **WHEN** `/community-engagement-platform/` is rendered and two published stories carry `community-engagement`
- **THEN** the page contains a "From the field" section with those two story cards and no other story

#### Scenario: Landing without matching stories
- **WHEN** `/for-educators/` is rendered and no published story carries `education`
- **THEN** the page contains no "From the field" section

#### Scenario: Draft stories are excluded
- **WHEN** a story carrying the landing's topic is unpublished
- **THEN** it does not appear in the block
