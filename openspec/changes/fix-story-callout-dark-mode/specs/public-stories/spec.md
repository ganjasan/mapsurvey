## ADDED Requirements

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
