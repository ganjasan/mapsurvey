# Auto-draft the public results page when a survey is published

## Why

Most creators never build a public results page: the config tab at
`/editor/surveys/<uuid>/public-results/` starts empty, so respondents get no "see what
others said" payoff and creators fall back to sharing the editor preview URL — whose
login wall converts their audience into fake platform signups (preview-link
registration trap, documented 2026-08-21). The per-question mapping already exists
(`_block_type_for_question`); the gap is only that nobody runs it over the whole
survey. Backlog #130, epic growth, Free tier.

## What Changes

- On a survey's transition to `published`, a draft `PublicResultsPage` is created (or
  an existing empty one populated) with one default block per aggregatable top-level
  question in survey order: geo questions → `map` blocks, choice/multichoice/rating/
  number/range → `chart` blocks. Free-text/datetime/html questions are skipped.
- The scaffold is deterministic, synchronous (no Celery, no AI) and idempotent: a new
  `PublicResultsPage.scaffolded_at` timestamp marks that scaffolding ran; blocks a
  creator deletes are never resurrected.
- Safety defaults: page stays `is_published=False` (publishing the results page
  remains an explicit creator action), `visibility='unlisted'`, `mode='live'`, k=3;
  map blocks start with `geo_label_fields=[]` (nothing but geometry in popups).
- The config tab shows a banner "we drafted this from your questions — review and
  publish" while the page is a scaffolded, still-unpublished draft; opening the
  config tab of an already-published survey also triggers the scaffold (covers
  surveys published via Django admin, which bypasses the editor transition view).
- The Share page links to the draft results page config once the survey is published.
- One-off backfill: management command `scaffold_public_results` (with `--dry-run`)
  drafts pages for already-published surveys that have none.

## Capabilities

### New Capabilities

- `public-results-scaffold`: automatic creation of a draft public results page with
  default blocks at publish time, its idempotency rules, safety defaults, editor
  banner, Share page link, and the backfill command.

### Modified Capabilities

<!-- none — the existing public-results rendering/editor behavior is unchanged;
     this change only adds an automatic way to produce the same rows a creator
     could create by hand -->

## Impact

- `survey/models.py` + one migration: `PublicResultsPage.scaffolded_at`
  (nullable DateTimeField).
- `survey/public_results.py`: new `scaffold_page(survey)` service function (lives
  beside `freeze_page`/`bump_page_version`); slug helper moves here or is reused
  from the editor module.
- `survey/editor_views.py` (`editor_survey_transition`): call scaffold under the
  existing `if new_status == 'published':` block.
- `survey/public_results_editor.py` (`public_results_config`): scaffold on first
  open when the survey is already published and the page was never scaffolded.
- `survey/templates/editor/public_results.html`: draft banner.
- `survey/share_views.py` + `survey/templates/editor/survey_share.html`: link to the
  results page draft in the published state.
- New `survey/management/commands/scaffold_public_results.py`.
- Tests in `survey/tests.py` (GIVEN/WHEN/THEN docstrings).
