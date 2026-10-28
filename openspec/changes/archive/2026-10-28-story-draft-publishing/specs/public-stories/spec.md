## MODIFIED Requirements

### Requirement: Stories are installed from the repository

A story SHALL be installed or refreshed from `survey/story_data/<slug>/` by `seed_story <slug>`.
A story installed for the first time SHALL be unpublished unless `--publish` is given. A re-run
SHALL keep the story's publication state unless `--publish` or `--draft` is given. A re-run SHALL
keep the row, its id and its `published_date`.

#### Scenario: Prepared story goes to production as a draft
- **WHEN** `seed_story <slug>` runs on a database without that story
- **THEN** the story exists, is unpublished, and is absent from the landing, `/stories/` and the sitemap

A story MAY be read from a directory outside the repository (`--from DIR`), so that text and
pictures a customer has not approved never reach the public repository.

#### Scenario: Refresh keeps a published story published
- **WHEN** `seed_story <slug>` runs again for a published story
- **THEN** it stays published with the same id and date

## ADDED Requirements

### Requirement: Publishing from the admin

Staff SHALL publish and unpublish stories from the Django admin: the list's publication
checkbox and the "Publish" / "Unpublish" actions. Publishing SHALL set `published_date` when it
is empty.

#### Scenario: Publish after the customer's OK
- **WHEN** staff run "Publish" on a draft story
- **THEN** it is published, dated, and appears on the landing and `/stories/`

### Requirement: Staff preview of a draft

An unpublished story SHALL return 404 to everyone except staff. Staff SHALL see it at its normal
URL with a "Draft — not public" banner and a `noindex` robots meta.

#### Scenario: Owner checks a draft on production
- **WHEN** a staff user opens `/stories/<slug>/` of an unpublished story
- **THEN** the page renders with the draft banner and noindex

#### Scenario: Visitor tries a draft URL
- **WHEN** an anonymous visitor opens it
- **THEN** the response is 404
