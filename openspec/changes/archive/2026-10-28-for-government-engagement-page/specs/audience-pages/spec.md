## ADDED Requirements

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
