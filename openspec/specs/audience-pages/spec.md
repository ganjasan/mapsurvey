# audience-pages Specification

## Purpose
TBD - created by archiving change audience-landing-pages. Update Purpose after archive.
## Requirements
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

### Requirement: Local-government / community-engagement page
The system SHALL serve a public page at `/for-government/` positioning Mapsurvey as an open-source
community engagement platform for local government, with engagement-intent SEO, a UTM-tagged CTA, and
an honest comparison pointer.

#### Scenario: Page renders with engagement positioning
- **WHEN** `/for-government/` is requested
- **THEN** it returns HTTP 200, presents the "community engagement platform" positioning, and its
  registration CTA carries `utm_source=government`

#### Scenario: Discoverable and navigable
- **WHEN** the site is crawled and rendered
- **THEN** `/for-government/` appears in sitemap.xml, robots.txt, the Solutions dropdown, and the footer

