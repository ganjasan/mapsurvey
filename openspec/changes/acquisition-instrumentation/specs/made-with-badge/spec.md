## ADDED Requirements

### Requirement: The badge appears on every respondent-facing surface
The "Made with Mapsurvey" badge SHALL render on the survey page, the thanks page and the public
results page `/r/<slug>/` for every survey, linking to the registration page with
`utm_source=viral_loop` and a `utm_medium` naming the surface (`survey`, `thanks`, `results`).

#### Scenario: Public results page carries the badge
- **WHEN** a visitor opens a public results page
- **THEN** the badge is present with `utm_source=viral_loop&utm_medium=results`

#### Scenario: Surfaces are distinguishable
- **WHEN** a visitor arrives at registration from the badge
- **THEN** `utm_medium` identifies which surface they came from

### Requirement: The badge link identifies no survey
The badge link SHALL contain no survey identifier, slug, or page-specific value, so a registration
attributed to the loop cannot be linked to the survey or results page it came from.

#### Scenario: Link inspected
- **WHEN** the badge is rendered on any surface
- **THEN** its `href` consists of the registration path and the two UTM parameters only
