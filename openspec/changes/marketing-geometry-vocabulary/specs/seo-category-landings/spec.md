## MODIFIED Requirements

### Requirement: Click-through titles and descriptions
The title of each of the four category pages and of `/alternatives/social-pinpoint/` SHALL start with the page's head term and name a hook (price, free, open source or map drawing) before the brand; the meta description SHALL be at most 160 characters and SHALL name the map input and the price or the free tier.

#### Scenario: Social Pinpoint alternative title
- **WHEN** `/alternatives/social-pinpoint/` is rendered
- **THEN** its `<title>` starts with "Social Pinpoint Alternative" and mentions drawing routes or areas, and its meta description mentions pins and that pricing is quote-only

#### Scenario: Category page description length
- **WHEN** any of the four category pages is rendered
- **THEN** its meta description is at most 160 characters long
