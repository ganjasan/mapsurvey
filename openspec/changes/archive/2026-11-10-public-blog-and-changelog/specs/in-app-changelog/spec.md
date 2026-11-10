## ADDED Requirements

### Requirement: The changelog is public
`/changelog/` SHALL list every changelog entry, newest first, to any visitor without signing in,
each with its date, New/Fixed tag, title, image and body, and an anchor equal to the entry id.
It SHALL NOT render the editor "Open" links or hero chips. `/changelog/feed.xml` SHALL be an
RSS 2.0 feed of the newest entries, each linking to `/changelog/#<id>` on the public host.

#### Scenario: Anonymous visitor reads the changelog
- **WHEN** an anonymous visitor opens `/changelog/`
- **THEN** the page lists the newest entry first, each inside an element whose id is the entry id

### Requirement: An entry links to the article that expands it
When a published blog article names an entry id in its `changelog` header, that entry SHALL show
a "Read the article" link to `/blog/<slug>/` on `/changelog/` and on `/editor/whats-new/`. A
draft article SHALL NOT produce the link.

#### Scenario: Entry with an article
- **GIVEN** a published article with `changelog: 2026-11-10-budget-questions`
- **WHEN** a creator opens `/editor/whats-new/`
- **THEN** the budget entry links to the article
