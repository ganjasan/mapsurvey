# Auto-draft the public results page when a survey is published

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: growth
**Tier**: Free
**Created**: 2026-08-21
**Related**: [AI audience plan](feature-ai-audience-plan.md) (#129), [Share flow dead-ends](improvement-share-flow-private-dead-end.md) (#128), [Public results map](feature-public-results-map.md) (#27), [Made-with-Mapsurvey viral loop](feature-made-with-mapsurvey-viral-loop.md)

## Description

When a survey is published, automatically create a *draft* `PublicResultsPage` with a
sensible default block per question (geo questions → map blocks, choice/multichoice →
charts, etc.), so the creator's job shrinks from "assemble a page from scratch" to
"review and hit publish". The draft is never auto-published — visibility stays a
deliberate creator action (k-anonymity and `geo_label_fields` review included).

Today the config tab at `/editor/surveys/<uuid>/public-results/` starts empty, and most
creators never build the page at all. That kills two loops at once: respondents get no
"see what others said" payoff, and the audience plan (#129) leans on `/r/<slug>/` as its
viral engine — a plan that says "share the live map" is useless when the map doesn't
exist.

## Evidence

- **Creators already improvise a public page — badly.** They share the *editor preview
  URL* with their audience because it is the only "look at my survey" link they can
  find; the login wall then converts their respondents into fake platform signups
  (documented 2026-08-21, preview-link registration trap). An auto-drafted `/r/<slug>/`
  is the link they were reaching for.
- Both surveys analysed for #129 (403 Ansouis, 440 Belo Horizonte) had no public
  results page. For 440 — a community map whose whole premise is "appear on the shared
  map" — the missing page removes the only self-sustaining recruitment mechanism.
- The mapping logic already exists: `_block_type_for_question` and
  `_get_or_create_page` in `survey/public_results_editor.py` — the feature is mostly
  "run the existing per-question mapping over the whole survey at publish time".

## Scope Sketch

- **Trigger**: first transition to `published` (or first open of the config tab, if the
  page doesn't exist yet — idempotent either way). No Celery needed: the scaffold is
  deterministic and cheap, a synchronous create is fine.
- **Deterministic scaffold, no AI in the core**: one block per aggregatable question in
  survey order — map block per geo question, chart per choice/multichoice/rating/range;
  skip free-text (individual answers are never published) and questions that look like
  PII (name/email by input semantics). Sensible defaults: `live` mode, `unlisted`
  visibility, k=3.
- **Draft state**: page exists but `is_published=False`; the config tab opens populated
  with a banner "we drafted this from your questions — review and publish". Publishing
  remains the existing explicit action (`public_results_set_published`).
- **Safety defaults for geo blocks**: `geo_label_fields` starts *empty* (nothing but
  geometry in popups) — the creator opts fields in, never out.
- **Surface it in the publish kit**: the Share page (#128/#129 home) links "your
  results page draft is ready" next to the tracked links.
- **Optional AI layer, later**: intro text / block captions in the survey's language
  via the existing `complete_structured()` plumbing — nice, not load-bearing. Ship the
  deterministic scaffold first.

## Open questions

- Backfill: also draft pages for already-published surveys without one (one-off
  management command), or new publishes only? Leaning backfill — that is where the 440
  case lives.
- Sub-questions of geo questions: include their aggregates as separate chart blocks, or
  leave them to the creator? Default-off keeps the draft short.
- Does the empty-state config tab disappear entirely, or stay for creators who delete
  the draft? (Deleting all blocks should not resurrect them on next publish —
  scaffolding must run only when no page row exists.)

## Notes

Promoted on 2026-08-22

## Status

Promoted.
