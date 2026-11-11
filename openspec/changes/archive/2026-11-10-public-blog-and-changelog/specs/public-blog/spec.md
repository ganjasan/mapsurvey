## ADDED Requirements

### Requirement: Articles are files in the repository
An article SHALL be a file `survey/blog/<YYYY-MM-DD>-<slug>.html` with a `---` header block and
an HTML body. The header SHALL carry `title`, `kind` (`feature` or `idea`) and `summary`, and MAY
carry `cover`, `cover_alt`, `author`, `topics`, `changelog`, `updated` and `draft`. The loader
SHALL refuse a file with a bad name, a missing required key, an unknown key or kind, an unknown
topic slug or an empty body, naming the file; a test over the shipped directories SHALL report a `changelog` id that names no changelog entry, and rendering SHALL ignore such an id;
a test SHALL load every file in the directory. Body pictures SHALL be written as
`{static:<path>}` tokens and rendered as static URLs.

#### Scenario: A valid article loads
- **WHEN** `survey/blog/2026-11-10-budget-questions.html` has a title, `kind: feature`, a summary and a body
- **THEN** the loader returns an article with slug `budget-questions`, date `2026-11-10` and URL `/blog/budget-questions/`

#### Scenario: A malformed article fails CI
- **WHEN** an article names `changelog: 2026-01-01-nothing` and no such entry exists
- **THEN** the shipped-directory test reports the file and the id

### Requirement: The blog feed lists stories and articles together
`/blog/` SHALL list published customer stories and published articles in one grid, newest first,
stories as story cards linking to `/stories/<slug>/` and articles as article cards linking to
`/blog/<slug>/`. Chips SHALL filter by kind (`?kind=stories|features|ideas`), offering only kinds
that have items; the canonical URL SHALL be `/blog/` for every filter.

#### Scenario: Mixed feed
- **GIVEN** a published story dated 2026-10-01 and a published feature article dated 2026-11-10
- **WHEN** a visitor opens `/blog/`
- **THEN** the article card comes first and the story card links to `/stories/<slug>/`

#### Scenario: Kind filter
- **WHEN** a visitor opens `/blog/?kind=features`
- **THEN** only feature articles are listed and the canonical is `https://mapsurvey.org/blog/`

### Requirement: The article page
`/blog/<slug>/` SHALL render the article's title, kind, summary, author, date (and updated date),
cover, topic chips linking to their landings, body, links to the changelog entries it expands,
and a `BlogPosting` JSON-LD block with a breadcrumb. An unknown slug SHALL 404.

#### Scenario: Article links its changelog entries
- **GIVEN** an article with `changelog: 2026-11-10-budget-questions`
- **WHEN** a visitor opens the article
- **THEN** the page links to `/changelog/#2026-11-10-budget-questions`

### Requirement: Draft articles are staff-only
An article with `draft: true` SHALL render only for staff, with a draft banner and
`noindex, nofollow`, SHALL answer 404 to everyone else, and SHALL be absent from `/blog/`, the
RSS feed and the sitemap.

#### Scenario: Anonymous visitor and a draft
- **WHEN** an anonymous visitor opens a draft article's URL
- **THEN** the response is 404

### Requirement: Blog RSS, sitemap and chrome
`/blog/feed.xml` SHALL be an RSS 2.0 feed of the newest published articles and stories with
absolute links on the public host; `/blog/` and `/changelog/` SHALL advertise their feeds with
`<link rel="alternate" type="application/rss+xml">`. The sitemap SHALL list `/blog/`,
`/changelog/` and every published article. The marketing nav SHALL link "Blog"; the footer's
Resources column SHALL link "Blog" and "Changelog".

#### Scenario: Sitemap lists articles
- **WHEN** `/sitemap.xml` is fetched
- **THEN** it contains `/blog/`, `/changelog/` and `/blog/<slug>/` of every published article and no draft
