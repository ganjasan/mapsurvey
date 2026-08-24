# Tasks: auto-draft-public-results

## 1. Model & migration

- [x] 1.1 Add `scaffolded_at` (nullable DateTimeField) to `PublicResultsPage` in
      `survey/models.py`; check `python manage.py showmigrations survey` leaf number
      against master before generating the migration
- [x] 1.2 Generate and apply the migration locally

## 2. Scaffold service

- [x] 2.1 Move/share slug + get-or-create logic: `scaffold_page(survey)` in
      `survey/public_results.py` using the block-type mapping from
      `public_results_editor` (single source of truth — import, don't duplicate)
- [x] 2.2 Implement scaffold rules: only when `scaffolded_at` is null and zero
      blocks; one block per publishable top-level question in `_survey_questions`
      order; `visibility='unlisted'` on page creation; stamp `scaffolded_at` in both
      the "scaffolded" and "already populated" branches; finish with
      `bump_page_version`

## 3. Call sites

- [x] 3.1 `editor_survey_transition`: call `scaffold_page` under
      `if new_status == 'published':`, wrapped so a scaffold error logs and never
      blocks the transition
- [x] 3.2 `public_results_config`: scaffold when `survey.status != 'draft'` and the
      page qualifies, before building context
- [x] 3.3 Management command `scaffold_public_results` with `--dry-run`, pattern
      after `purge_trashed_surveys.py`; targets non-deleted canonical
      published/closed surveys

## 4. UI

- [x] 4.1 Draft banner in `survey/templates/editor/public_results.html`
      (`pr-banner` pattern; shown when `page.scaffolded_at` and not
      `page.is_published`); `{% comment %}` only, run the template-comment guard
      test right after editing
- [x] 4.2 Share page: results-page link in the published branch of
      `survey/templates/editor/survey_share.html` (+ context in
      `survey/share_views.py`): config-tab link while unpublished, `/r/<slug>/`
      once published

## 5. Tests (GIVEN/WHEN/THEN docstrings)

- [x] 5.1 Scaffold service unit tests: first publish populates; lazily created
      empty page populated; deleted blocks not resurrected on re-publish;
      hand-built page untouched; defaults (unlisted, is_published=False,
      geo_label_fields=[])
- [x] 5.2 Transition view test: publish triggers scaffold; scaffold failure does
      not block transition
- [x] 5.3 Config-tab test: admin-published survey scaffolds on first open; banner
      renders for draft and disappears after page publish
- [x] 5.4 Share page test: link to config tab when draft, to `/r/<slug>/` when
      published
- [x] 5.5 Backfill command test: dry-run writes nothing; live run scaffolds;
      re-run is a no-op
- [x] 5.6 Run `./run_tests.sh survey` once as baseline delta check
