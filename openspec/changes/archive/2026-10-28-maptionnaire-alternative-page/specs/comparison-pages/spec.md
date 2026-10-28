## ADDED Requirements

### Requirement: Maptionnaire alternative comparison page
The system SHALL serve a public page at `/alternatives/maptionnaire/` presenting Mapsurvey as a
free, open-source alternative to Maptionnaire, with a comparison table and a balanced
"when Maptionnaire may fit better" section. Competitor claims SHALL be factual.

#### Scenario: Page renders
- **WHEN** an anonymous visitor requests `/alternatives/maptionnaire/`
- **THEN** it returns HTTP 200 with the comparison content

### Requirement: Alternative-intent SEO
The page SHALL set an alternative-intent title, meta description, canonical URL and Open Graph tags,
and SHALL be listed in `sitemap.xml` and allowed in `robots.txt`.

#### Scenario: SEO + discoverability
- **WHEN** the page, sitemap.xml, and robots.txt are fetched
- **THEN** the page carries a canonical `/alternatives/maptionnaire/`, and both sitemap and robots reference it

### Requirement: Attribution on comparison CTAs
Registration CTAs SHALL carry `utm_source=comparison`, and the page SHALL capture first-touch source.

#### Scenario: Comparison UTM present
- **WHEN** the page renders
- **THEN** its registration link includes `utm_source=comparison`
