## ADDED Requirements

### Requirement: The sitemap rework preserves the publicly-visible filter
The sitemap generator SHALL keep computing the set of advertised surveys through the
single shared publicly-visible function when it is reworked to emit language variants.
Language support SHALL NOT introduce a second, re-expressed filter.

#### Scenario: Survey filtering is unchanged by localization
- **GIVEN** the sitemap emits language variants for marketing URLs
- **WHEN** `/sitemap.xml` is fetched
- **THEN** the `/surveys/<uuid>/` entries SHALL be exactly those the shared
  publicly-visible function returns, unchanged from before localization

#### Scenario: No language prefix reaches survey entries
- **WHEN** `/sitemap.xml` is fetched
- **THEN** no `/surveys/<uuid>/` entry SHALL carry a language prefix

#### Scenario: Every advertised localized URL is reachable
- **WHEN** `/sitemap.xml` is fetched and each language-prefixed marketing entry is
  requested anonymously
- **THEN** no entry SHALL respond with `404`

### Requirement: Language variants are not treated as duplicate content
The platform SHALL distinguish language variants of a marketing page from duplicates, by
pairing each variant's self-referencing canonical with a reciprocal `hreflang` set.

#### Scenario: Variants reference each other
- **GIVEN** a marketing page published in English and German
- **WHEN** either variant is fetched
- **THEN** it SHALL declare a canonical pointing at itself and `hreflang` entries naming
  both variants

#### Scenario: A variant without reciprocal markup is not advertised
- **GIVEN** a language variant whose `hreflang` set is incomplete
- **WHEN** `/sitemap.xml` is fetched
- **THEN** that variant SHALL NOT appear
