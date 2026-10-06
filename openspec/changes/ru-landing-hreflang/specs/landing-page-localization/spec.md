## ADDED Requirements

### Requirement: Russian homepage at /ru/
The system SHALL serve the homepage in Russian at `/ru/` to every visitor, anonymous or signed in, with the same sections as `/`. The page SHALL declare `<html lang="ru">`, send `Content-Language: ru`, and carry `https://mapsurvey.org/ru/` as its canonical URL. The language of `/ru/` SHALL NOT depend on the visitor's `Accept-Language`, language cookie or creator preference, and `/` SHALL stay English under the same conditions.

#### Scenario: Russian homepage renders in Russian
- **WHEN** an anonymous visitor requests `/ru/`
- **THEN** the response is 200 with `<html lang="ru">`, `Content-Language: ru`, a Russian `<title>` and Russian hero headline
- **AND** the canonical link is `https://mapsurvey.org/ru/`

#### Scenario: English homepage is unaffected by a Russian browser
- **WHEN** a visitor whose `Accept-Language` is `ru` and whose language cookie is `ru` requests `/`
- **THEN** the page is English with `<html lang="en">`

#### Scenario: Russian homepage ignores an English browser
- **WHEN** a visitor whose `Accept-Language` is `en` requests `/ru/`
- **THEN** the page is Russian

### Requirement: The Russian homepage is fully translated
Every string the `/ru/` page renders from the application's catalog SHALL have a non-empty Russian translation that is not marked fuzzy, so no English template text appears on the page. Database content (story titles and summaries) is exempt.

#### Scenario: No untranslated template string on /ru/
- **WHEN** the msgids used by `landing.html`, `base_landing.html` and `partials/_story_card.html` are looked up in the `ru` catalog
- **THEN** each has a non-empty msgstr and none is flagged fuzzy

### Requirement: Language alternates on marketing pages
Every page built on `base_landing.html` SHALL declare its language alternates with `<link rel="alternate" hreflang>`. The homepage pair (`/` and `/ru/`) SHALL each carry the same three alternates: `en` → `https://mapsurvey.org/`, `ru` → `https://mapsurvey.org/ru/`, `x-default` → `https://mapsurvey.org/`. Every other marketing page SHALL carry `en` and `x-default`, both pointing at its own canonical URL.

#### Scenario: Homepage pair declares reciprocal alternates
- **WHEN** `/` or `/ru/` is rendered
- **THEN** the head contains exactly the `en`, `ru` and `x-default` alternates listed above

#### Scenario: Audience page declares itself as the English and default version
- **WHEN** `/for-planners/` is rendered
- **THEN** the head contains `hreflang="en"` and `hreflang="x-default"` links to `https://mapsurvey.org/for-planners/`
- **AND** no `hreflang="ru"` link

### Requirement: Language switcher between the homepage versions
The homepage pair SHALL show an EN / RU switcher in the navbar made of plain links to `/` and `/ru/`, marking the current language. Every page built on `base_landing.html` SHALL link to `/ru/` from the footer with the label "Русский".

#### Scenario: Switcher on the English homepage
- **WHEN** `/` is rendered
- **THEN** the navbar marks EN as current and links RU to `/ru/`

#### Scenario: Switcher on the Russian homepage
- **WHEN** `/ru/` is rendered
- **THEN** the navbar marks RU as current and links EN to `/`

#### Scenario: Footer link from an English-only page
- **WHEN** `/trust/` is rendered
- **THEN** the footer contains a link to `/ru/` labelled "Русский"

### Requirement: In-page links on the Russian homepage stay on it
On `/ru/`, the navbar brand and the Features and Demo links SHALL point to `/ru/` and its anchors, not to the English homepage. On every other marketing page they SHALL keep pointing to `/`.

#### Scenario: Anchors on /ru/
- **WHEN** `/ru/` is rendered
- **THEN** the Features link is `/ru/#features` and the brand links to `/ru/`

#### Scenario: Anchors elsewhere
- **WHEN** `/for-planners/` is rendered
- **THEN** the Features link is `/#features`
