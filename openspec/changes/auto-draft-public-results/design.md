# Design: auto-draft-public-results

## Context

The public results system is complete and shipped: `PublicResultsPage` (1:1 with the
canonical `SurveyHeader`), ordered `PublicResultsBlock`s, rendering in
`survey/public_results.py`, editor views in `survey/public_results_editor.py`. The
per-question mapping (`_block_type_for_question`: point/line/polygon → `map`;
choice/multichoice/rating/number/range → `chart`; everything else unpublishable) and
the question iteration order (`_survey_questions`: top-level questions ordered by
`survey_section__id, order_number`) already exist. Two facts shape the design:

- The config tab **already lazily creates** the page row (`_get_or_create_page` in
  `public_results_config`) — with zero blocks. So "no page row" is not a usable
  "never scaffolded" signal.
- A survey can become `published` on two paths: `editor_survey_transition`
  (the product path, with audit + PostHog event) and Django admin (staff flips
  `status` directly, bypassing the view).

## Goals / Non-Goals

**Goals:**
- Every survey that reaches `published` ends up with a populated draft results page
  the creator only has to review and publish.
- Idempotency: scaffolding runs at most once per page; creator deletions are final.
- Zero behavior change for pages a creator already built by hand.

**Non-Goals:**
- No AI content (intro texts, captions) — deterministic scaffold only; the AI layer
  is a later, separate change.
- No auto-publishing: `is_published` stays `False`; `/r/<slug>/` reachability is
  unchanged until the creator acts.
- No blocks for sub-questions (their aggregates stay creator-added; geo sub-questions
  remain available as `geo_label_fields`, which start empty).
- No signals / `SurveyHeader.save()` override to catch the admin path (see Decisions).

## Decisions

1. **Service function in `survey/public_results.py`, not in the editor views module.**
   `scaffold_page(survey)` lives beside `freeze_page`/`bump_page_version` — it is
   page-lifecycle logic, not a view. It reuses the slug + get-or-create logic
   (moved/shared with `public_results_editor._get_or_create_page`) and the
   `_block_type_for_question` mapping (imported or moved — single source of truth,
   no duplicated input-type lists). Alternative considered: keep everything in
   `public_results_editor.py` and import it from `editor_views.py` — rejected as
   view→view coupling.

2. **`scaffolded_at` timestamp on `PublicResultsPage` (nullable DateTimeField), one
   migration.** Scaffold runs only when `scaffolded_at IS NULL` **and** the page has
   zero blocks; it always stamps `scaffolded_at` when it runs. This covers lazily
   created empty pages (they get a draft) while deleted blocks never resurrect (the
   stamp persists). Alternatives rejected: "no page row" (misses every creator who
   ever opened the tab), "zero blocks" alone (resurrects deleted blocks on
   re-publish — explicit backlog requirement violation). Pages that already have
   hand-built blocks but no stamp are stamped-without-scaffolding on first
   opportunity? No — simpler: the zero-blocks condition alone protects them; the
   stamp is only written when scaffolding actually runs or is intentionally skipped
   as already-populated (stamping in that case is harmless and stops repeat checks;
   implementation stamps in both branches).

3. **Three call sites, no signals.**
   - `editor_survey_transition` — inside the existing
     `if new_status == 'published':` block, after `survey.save()`. Synchronous:
     the scaffold is a handful of cheap INSERTs.
   - `public_results_config` — when `survey.status != 'draft'` and the page
     qualifies, scaffold before rendering. This de-facto covers the admin path:
     however the survey became published, the creator's first look at the tab shows
     the draft. It also upgrades the backfill cohort lazily.
   - `scaffold_public_results` management command — eager backfill for
     already-published surveys (case #440), `--dry-run` supported, pattern follows
     `purge_trashed_surveys.py` (thin BaseCommand over the shared service function).
   Signals / `save()` diffing rejected: the codebase uses neither, and status-diff
   detection in `save()` is fragile.

4. **Scaffold content and defaults.** One block per publishable top-level question in
   `_survey_questions` order, `order` = running index, `viz='auto'`,
   `basemap='streets'` (model defaults), `geo_label_fields=[]` for maps. Page
   defaults: `mode='live'`, `k_anonymity_threshold=3` (model defaults) — but
   `visibility='unlisted'` set explicitly (model default is `public`; the backlog
   mandates unlisted-until-reviewed). Finish with one `bump_page_version(page)`.
   Only the canonical survey is scaffolded (`versioning.publish_draft` never flips
   `status`, so version publishing cannot re-trigger it).

5. **PII skip is the existing type filter.** Free-text (`text`, `text_line`),
   `datetime`, `html`, `image`, `ranking` map to no block type today, so
   name/email-style questions (always text inputs) are excluded by construction. No
   extra name-based heuristics — they'd be locale-dependent guesswork.

6. **UI surfacing.**
   - Config tab: a `pr-banner`-style notice (same pattern as the existing
     "publish the survey first" banner in `public_results.html`) shown when
     `page.scaffolded_at` is set and `page.is_published` is `False`:
     "We drafted this page from your questions — review and publish."
   - Share page: in the published branch of `survey_share.html`, a link
     "Your results page draft is ready — review & publish" →
     `/editor/surveys/<uuid>/public-results/`; once `page.is_published`, it becomes
     the `/r/<slug>/` link. Django template comments: `{% comment %}` only, never
     multi-line `{# #}`.

## Risks / Trade-offs

- [Scaffold at transition adds writes to the publish request] → a handful of INSERTs
  inside one request; no Celery needed. If it ever fails, the config-tab call site
  is a natural retry — wrap the transition-time call so a scaffold error never
  blocks the status change itself (log + continue).
- [Creator with a hand-built page gets stamped, never scaffolded] → intended;
  zero-blocks guard protects their work.
- [Backfill creates pages for abandoned surveys] → drafts are invisible
  (`is_published=False`); no public surface changes.
- [Migration numbering collision with parallel worktrees] → check `showmigrations`
  leaves before merge (standing project rule).

## Migration Plan

1. Deploy migration (`scaffolded_at`, nullable — zero-downtime safe, no backfill of
   the column itself).
2. Feature is active immediately for new publishes; no kill switch needed — the
   scaffold only creates invisible draft rows, and the worst-case failure mode is
   "no draft", i.e. today's behavior. (Merge reaches prod in minutes; this failure
   containment is the safety argument.)
3. Run `python manage.py scaffold_public_results --dry-run`, review, then run live.
4. Rollback: revert code; existing scaffolded drafts are inert data and can stay.

## Open Questions

None — resolved during clarification: `scaffolded_at` mechanics, backfill in-scope,
sub-question blocks default-off.
