## ADDED Requirements

### Requirement: SEO meta tags in page head
The landing page SHALL include optimized meta tags in the `<head>` element.

#### Scenario: Title tag
- **WHEN** the landing page is rendered
- **THEN** the `<title>` SHALL be "Mapsurvey — Open-Source Participatory Mapping Platform | Free PPGIS Tool"

#### Scenario: Meta description
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include a `<meta name="description">` tag with content describing Mapsurvey as a free, open-source, self-hostable map-based survey platform and Maptionnaire alternative

#### Scenario: Meta keywords
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include a `<meta name="keywords">` tag with terms: PPGIS, participatory mapping, open source GIS, map survey, spatial data collection, urban planning tool, community engagement

### Requirement: Open Graph tags for social sharing
The landing page SHALL include Open Graph meta tags for rich social media previews.

#### Scenario: OG tags present
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include `og:title`, `og:description`, `og:image`, `og:type` (website), and `og:url` meta tags

#### Scenario: OG image
- **WHEN** the landing page is rendered
- **THEN** the `og:image` tag SHALL reference a 1280x640 social preview image showing the product interface with a map

### Requirement: Twitter Card tags
The landing page SHALL include Twitter Card meta tags.

#### Scenario: Twitter card type
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include `<meta name="twitter:card" content="summary_large_image">`

### Requirement: Schema.org structured data
The landing page SHALL include JSON-LD structured data describing Mapsurvey as a SoftwareApplication.

#### Scenario: JSON-LD script
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include a `<script type="application/ld+json">` element with Schema.org SoftwareApplication data including: name, applicationCategory, operatingSystem, offers (price 0, USD), description, license (AGPLv3 URL), and codeRepository (GitHub URL)

### Requirement: Hreflang tags for multilingual support
The landing page SHALL include hreflang link tags for language variants.

#### Scenario: EN and RU hreflang
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include `<link rel="alternate" hreflang="en">` and `<link rel="alternate" hreflang="ru">` tags pointing to the respective language versions

#### Scenario: x-default hreflang
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include `<link rel="alternate" hreflang="x-default">` pointing to the English version

### Requirement: Canonical URL
The landing page SHALL include a canonical link tag.

#### Scenario: Canonical tag
- **WHEN** the landing page is rendered
- **THEN** the page SHALL include `<link rel="canonical" href="https://mapsurvey.org/">` (or the configured domain)
