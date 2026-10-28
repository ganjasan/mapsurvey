## ADDED Requirements

### Requirement: Urban-planners landing page
The system SHALL serve a public page at `/for-planners/` positioning Mapsurvey for map-based
community engagement and public consultation, with planner-intent SEO and a UTM-tagged CTA.

#### Scenario: Planners page renders
- **WHEN** `/for-planners/` is requested
- **THEN** it returns HTTP 200 with planner positioning and a registration CTA carrying `utm_source=planners`

### Requirement: Researchers landing page
The system SHALL serve a public page at `/for-researchers/` positioning Mapsurvey for participatory
mapping (PPGIS) and citizen-science research, with researcher-intent SEO and a UTM-tagged CTA.

#### Scenario: Researchers page renders
- **WHEN** `/for-researchers/` is requested
- **THEN** it returns HTTP 200 with research positioning and a registration CTA carrying `utm_source=researchers`

### Requirement: Discoverable and navigable
Both pages SHALL be listed in `sitemap.xml`, allowed in `robots.txt`, and linked from the Solutions
nav dropdown and the footer.

#### Scenario: In sitemap, robots, and nav
- **WHEN** the site is crawled and rendered
- **THEN** both `/for-planners/` and `/for-researchers/` appear in sitemap.xml, robots.txt, and the nav
