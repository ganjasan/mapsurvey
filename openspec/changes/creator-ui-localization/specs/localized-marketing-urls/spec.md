## ADDED Requirements

### Requirement: Marketing pages are served at language-prefixed URLs
The system SHALL serve localized marketing pages under a language path prefix, while
keeping English on its existing unprefixed URLs.

#### Scenario: English keeps its current URL
- **WHEN** a visitor requests `/for-planners/`
- **THEN** the English page MUST be served at that exact path, with no redirect

#### Scenario: A localized page is served under its prefix
- **WHEN** a visitor requests `/de/for-planners/`
- **THEN** the German version of that page MUST be served

#### Scenario: Landing root per language
- **WHEN** a visitor requests `/de/`
- **THEN** the German landing page MUST be served, and `/` MUST remain English

### Requirement: Editor and respondent URLs are never language-prefixed
The system SHALL NOT apply language prefixes to editor or respondent URLs, because
respondent links are already distributed and their language comes from the survey.

#### Scenario: Respondent survey links are unchanged
- **WHEN** the URL configuration is loaded
- **THEN** `/surveys/<uuid>/` MUST resolve without a language prefix and MUST NOT redirect
  to a prefixed variant

#### Scenario: Editor URLs are unchanged
- **WHEN** a signed-in creator navigates the editor
- **THEN** editor URLs MUST remain unprefixed regardless of the creator's language

#### Scenario: Public results pages are unchanged
- **WHEN** a visitor opens `/r/<slug>/`
- **THEN** the URL MUST remain unprefixed

### Requirement: Localized pages declare hreflang and a self-referencing canonical
The system SHALL emit a complete `hreflang` set and a self-referencing canonical on every
localized marketing page, so search engines associate the language variants correctly.

#### Scenario: hreflang covers every published language of that page
- **WHEN** a localized marketing page is rendered
- **THEN** it MUST emit one `hreflang` link per published language of that page, plus
  `x-default` pointing at the English URL

#### Scenario: Canonical points at the page's own language
- **WHEN** the German version of a page is rendered
- **THEN** its canonical URL MUST be the German URL, not the English one

#### Scenario: Unpublished languages are excluded
- **WHEN** a page has no Portuguese translation yet
- **THEN** no Portuguese `hreflang` entry MUST be emitted for that page

### Requirement: The sitemap lists every published language variant
The system SHALL emit one sitemap entry per published language for each marketing URL,
while leaving non-marketing URLs single-entry.

#### Scenario: Marketing URLs are emitted per language
- **WHEN** the sitemap is generated and a landing page is published in English and German
- **THEN** the sitemap MUST contain both the unprefixed English URL and the `/de/` URL

#### Scenario: Survey and results URLs are not multiplied
- **WHEN** the sitemap is generated
- **THEN** `/surveys/<uuid>/` and `/r/<slug>/` entries MUST appear exactly once each,
  without language prefixes

#### Scenario: A language absent from a page is absent from the sitemap
- **WHEN** a marketing page has no Polish translation
- **THEN** no Polish URL for that page MUST appear in the sitemap

### Requirement: A language goes live only when its localization is complete
The system SHALL withhold a language variant of a marketing page from the sitemap and the
`hreflang` graph until that page's copy, canonical and `hreflang` entries are all present.

#### Scenario: Partially translated language is not advertised
- **WHEN** a language has translated copy but no canonical or `hreflang` wiring
- **THEN** its URLs MUST NOT be listed in the sitemap or referenced by `hreflang`

#### Scenario: Languages roll out independently
- **WHEN** German copy is complete and Portuguese is not
- **THEN** German URLs MUST be published while Portuguese URLs stay withheld
