## ADDED Requirements

### Requirement: The landing page is available in each supported language
The system SHALL serve a localized landing page for every language whose copy is
complete, keeping the English landing page at `/`.

#### Scenario: Localized landing is served
- **WHEN** an unauthenticated visitor navigates to `/de/`
- **THEN** the system renders the landing page in German, with the same sections as the
  English page

#### Scenario: English landing keeps the root URL
- **WHEN** a visitor navigates to `/`
- **THEN** the system renders the English landing page without redirecting to a
  language-prefixed URL

#### Scenario: Incomplete language is not served
- **WHEN** a language has no completed landing copy
- **THEN** its landing URL MUST NOT be published, advertised in the sitemap, or referenced
  by `hreflang`

### Requirement: Landing copy is authored per language, not machine-translated
Localized marketing copy SHALL be authored in the target language using the professional
register of participation and planning, because that vocabulary carries terms a municipal
reader expects and a literal rendering does not.

#### Scenario: Copy carries the domain term, not a literal rendering
- **WHEN** German landing copy refers to public participation
- **THEN** it MUST use the term used in that field rather than a literal translation of
  the English phrase

#### Scenario: Publishing a language is an explicit decision
- **WHEN** a language's copy is complete
- **THEN** publishing it MUST be a deliberate act rather than an automatic consequence of
  the copy existing, because terminology review is organised separately from this change

### Requirement: Visitors can reach other language versions of a marketing page
The system SHALL provide a visible affordance on marketing pages for moving between the
published language versions of that page.

#### Scenario: Switching language stays on the same page
- **WHEN** a visitor on `/for-planners/` selects Deutsch
- **THEN** the system MUST navigate to `/de/for-planners/`, not to the landing root

#### Scenario: Only published languages are offered
- **WHEN** the affordance is rendered on a page translated into English and German only
- **THEN** it MUST offer exactly those two languages
