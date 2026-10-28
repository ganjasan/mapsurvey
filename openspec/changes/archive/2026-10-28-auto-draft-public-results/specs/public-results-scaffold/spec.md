# public-results-scaffold

## ADDED Requirements

### Requirement: Draft results page is scaffolded on publish
When a survey transitions to `published` via the editor, the system SHALL ensure a
`PublicResultsPage` exists for the survey and SHALL populate it with one default
block per publishable top-level question in survey order (sections by id, then
question `order_number`): geo questions (`point`, `line`, `polygon`) produce `map`
blocks; `choice`, `multichoice`, `rating`, `number`, `range` questions produce
`chart` blocks. Questions of other input types and sub-questions SHALL NOT produce
blocks. A scaffold failure SHALL NOT block the status transition itself.

#### Scenario: First publish creates a populated draft
- **WHEN** a survey with a point question, a choice question and a text question is
  transitioned from `draft` to `published` and no results page exists
- **THEN** a `PublicResultsPage` is created with exactly two blocks — a `map` block
  for the point question and a `chart` block for the choice question, in survey
  order — and `scaffolded_at` is set

#### Scenario: Lazily created empty page is populated
- **WHEN** the creator previously opened the config tab (page row exists with zero
  blocks, `scaffolded_at` is null) and the survey is then published
- **THEN** the existing page is populated with default blocks and `scaffolded_at`
  is set

### Requirement: Scaffolding is idempotent and never resurrects deleted blocks
The system SHALL scaffold a page only when `scaffolded_at` is null AND the page has
zero blocks. Once `scaffolded_at` is set, scaffolding SHALL never run again for that
page, regardless of later status transitions.

#### Scenario: Deleted blocks stay deleted on re-publish
- **WHEN** a creator deletes all scaffolded blocks, moves the survey to `closed` and
  back to `published`
- **THEN** no blocks are recreated

#### Scenario: Hand-built page is left untouched
- **WHEN** a survey whose page already contains creator-built blocks (and
  `scaffolded_at` is null) is published
- **THEN** the existing blocks are unchanged and no default blocks are added

### Requirement: Scaffolded draft is invisible until the creator publishes it
A scaffolded page SHALL have `is_published=False`, `visibility='unlisted'`,
`mode='live'`, `k_anonymity_threshold=3`, and every scaffolded `map` block SHALL
have `geo_label_fields=[]`. Publishing the results page SHALL remain the existing
explicit creator action.

#### Scenario: Public URL stays gated after scaffold
- **WHEN** a survey is published and its results page is scaffolded
- **THEN** `/r/<slug>/` still returns 404 until the creator publishes the page

### Requirement: Config tab scaffolds already-published surveys
The system SHALL scaffold a qualifying page (`scaffolded_at` null, zero blocks)
when the config tab is opened for a survey whose status is not `draft`, before
rendering, so surveys published outside the editor (e.g. Django admin) also
receive a draft.

#### Scenario: Admin-published survey gets a draft on first config visit
- **WHEN** a survey's status was set to `published` directly in Django admin and the
  creator opens `/editor/surveys/<uuid>/public-results/`
- **THEN** the page renders with the scaffolded default blocks

### Requirement: Draft banner in the config tab
While a page has `scaffolded_at` set and `is_published=False`, the config tab SHALL
display a notice that the page was drafted automatically from the survey's questions
and needs review before publishing.

#### Scenario: Banner shows for an unreviewed draft
- **WHEN** the creator opens the config tab of a freshly scaffolded page
- **THEN** the draft notice is visible

#### Scenario: Banner disappears after the creator publishes the page
- **WHEN** the creator publishes the results page
- **THEN** the draft notice is no longer rendered

### Requirement: Share page links to the results page draft
For a published survey, the Share page SHALL link to the results page: to the config
tab ("review & publish" wording) while the page is unpublished, and to the public
`/r/<slug>/` URL once it is published.

#### Scenario: Share page of a published survey with an unpublished draft
- **WHEN** the creator opens the Share page after publishing the survey
- **THEN** a link to `/editor/surveys/<uuid>/public-results/` is shown

### Requirement: Backfill command for already-published surveys
A management command `scaffold_public_results` SHALL scaffold pages for all
non-deleted canonical surveys with status `published` or `closed` that qualify
(`scaffolded_at` null, zero blocks), SHALL support `--dry-run` (report without
writing), and SHALL be safe to re-run.

#### Scenario: Dry run reports without writing
- **WHEN** the command runs with `--dry-run` against a published survey without a
  results page
- **THEN** the survey is listed as a candidate and no page or blocks are created

#### Scenario: Re-run is a no-op
- **WHEN** the command runs twice
- **THEN** the second run creates nothing
