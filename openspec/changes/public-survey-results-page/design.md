## Context

Mapsurvey already has a full editor-only analytics dashboard. The data layer is `SurveyAnalyticsService` (`survey/analytics.py`), which exposes everything a public page needs:

- `get_overview()` — response counts.
- `get_all_question_stats()` / `get_question_stats(question)` — per-question chart-ready aggregates.
- `get_geo_feature_collection()` — GeoJSON for the map (points/lines/polygons + heatmaps).
- Clean-session filtering (`is_deleted=False`, validation status) already applied for the dashboard.

The only existing public-publishing primitive is the `Story` model (`survey/models.py:625`), a generic CMS page (`article`/`map`/`results`) with a static `body`, surfaced at `/stories/<slug>/` and listed via `views.survey_list`. It is hand-authored in Django admin and disconnected from live data — insufficient for a curated, live results page bound 1:1 to a survey.

Surveys have a lifecycle (`status`: draft→testing→published→closed→archived), an optional password gate, and versioning (`canonical_survey`, `is_canonical`, `published_version`). Sessions aggregate against the canonical survey. The editor is HTMX + SortableJS, no SPA.

Constraints: GeoDjango/PostGIS; multilingual content stored as `{"en": ..., "ru": ...}` JSON (see `thanks_html`); GDPR sensitivity already reflected in code (`AbuseEvent` deliberately avoids storing PII).

## Goals / Non-Goals

**Goals:**
- A creator-curated, publicly shareable page of aggregated survey results, bound 1:1 to a survey.
- Hybrid live/frozen data, reusing `SurveyAnalyticsService` with no contract change.
- Anonymous geo display with creator-controlled popup fields; never expose record-level identifiers or individual text answers.
- Public/Unlisted visibility with correct SEO (index vs noindex).
- Privacy guards: clean-session-only source, k-anonymity masking of small buckets.
- Engagement affordances: response counter, "Take the survey" CTA, "Made with Mapsurvey" footer.

**Non-Goals:**
- Publishing individual text answers (deferred; would need moderation).
- A public comment-map / per-response moderation queue (future).
- Password-protected results (Unlisted ≠ private; truly private results are out of scope).
- Replacing or merging the `Story` model. Optional listing integration only.
- Custom theming / white-label of the public page beyond intro text and block selection.

## Decisions

### D1: New `PublicResultsPage` (1:1 with `SurveyHeader`) + `PublicResultsBlock`
Chosen over fields-on-`SurveyHeader` (no room for snapshot/curated block order, model bloat) and over extending `Story` (generic CMS; live config muddies its responsibility).

- `PublicResultsPage`: `survey` (OneToOne), `slug` (unique), `visibility` (`public`|`unlisted`), `is_published`, `intro` (JSON multilingual), `mode` (`live`|`frozen`), `snapshot` (JSON, null), `frozen_at`, `show_response_count`, `show_participate_cta`, `k_anonymity_threshold` (int, default 3), timestamps.
- `PublicResultsBlock`: `page` (FK), `question` (FK, null for text/image blocks), `block_type` (`chart`|`map`|`text`|`image`), `viz` (`auto`|`bar`|`pie`|`heatmap`|…), `custom_title` (JSON, optional), `content` (JSON: text body or image caption), `image` (ImageField, `image` blocks only), `geo_label_fields` (JSON list), `basemap` (`streets`|`satellite`|`topo`, map blocks), `order` (int).

Rationale: clean separation, directly supports the hybrid + freeze + curation requirements; keeps `SurveyHeader` lean.

### D2: Render live and frozen through one block contract
Live blocks call `SurveyAnalyticsService`. Freeze serializes the **same per-block payload** into `snapshot`. The block template is identical for both modes — frozen rendering reads `snapshot`, live reads the service. Avoids template duplication and guarantees parity.

Alternative rejected: separate frozen renderer → drift risk between live and frozen output.

### D3: Short public URL `/r/<slug>/` (default decision, was open)
A short top-level prefix optimizes social sharing and OG previews. Alternatives: `/surveys/<slug>/results/` (couples to survey slug, longer) or reuse `/stories/` (conflates with the Story CMS). `/r/` is a new top-level pattern in `survey/urls.py`; `slug` is independent of the survey slug so it can be vanity/stable.

### D4: k-anonymity threshold, default K=3 (default decision, was open)
Buckets (choice counts, cross-tabs) with `0 < count < K` render as "<K" instead of an exact number, preventing deanonymization of a lone respondent from a public chart. Stored per page (`k_anonymity_threshold`), default 3, creator-adjustable (min 1 = off). Applied in a thin presentation wrapper over the service output, not in the service itself (keeps dashboard behavior unchanged).

Alternative rejected: dropping k-anonymity from MVP → unacceptable re-identification risk for small/geographically narrow surveys, which is exactly our civic use case.

### D5: Live cache TTL 60s (default decision, was open)
Live mode wraps the service call in Django `cache` keyed by `slug` + `lang` + `mode`, 60s TTL. Protects the DB from viral traffic; a 60s lag on the response counter is acceptable. Invalidation is purely TTL-based (no per-answer invalidation) for simplicity. Frozen mode never hits the DB or cache (reads `snapshot`).

### D6: Data source = clean sessions on the canonical survey
Reuse the dashboard's clean-session filter (`is_deleted=False`, valid status). Aggregate against the canonical survey (`is_canonical=True`) so version transitions don't reset counts. Editor moderation of junk sessions automatically cleans the public page.

### D7: Visibility = SEO + listing, not security
`public` → `<meta robots=index>`, eligible for the `/stories/` listing and `sitemap.xml`. `unlisted` → `noindex`, excluded from listing/sitemap, reachable only by direct (unguessable) slug. Documented explicitly as obscurity, not access control.

### D8: Text questions excluded from publishable blocks
The block-add picker marks text/text_line questions as "not available for publication." No raw individual texts ever reach the public page. (Word-frequency/word-cloud aggregation is a possible future block type.)

## Risks / Trade-offs

- [Live aggregation under viral traffic could overload PostGIS] → 60s cache (D5); frozen mode for high-stakes/high-traffic launches.
- [k-anonymity gives false sense of full anonymity for geo points] → masking applies to count buckets; geo points are separately anonymized via `geo_label_fields` (default empty popup). Document the distinction for creators.
- [Unlisted slug leaks → results exposed] → accept as documented obscurity; offer freeze so a leaked link shows a controlled snapshot, not live raw aggregates. Truly-private results are a separate future change.
- [Snapshot format drift if service output changes later] → snapshot stores the rendered block payload (versioned by a `snapshot_version` field); on read, unknown versions fall back to a "re-freeze needed" notice rather than crashing.
- [Deleted question still referenced by a block] → block renders nothing (silently skipped), never 500.
- [New top-level `/r/` route collides with future routing] → namespace is short but reserved; documented in urls.

## Migration Plan

1. One Django migration adding `PublicResultsPage` and `PublicResultsBlock`. No changes to existing tables.
2. Purely additive: default state is `is_published=False`, so no existing survey exposes anything until a creator opts in.
3. Deploy is config-free (no new env vars; reuses existing cache backend). Render PR preview validates.
4. Rollback: feature is gated by `is_published`; reverting the migration is safe since no existing model depends on the new tables. URLs and templates are additive.

## Open Questions

- Should a `public` results page be auto-added to the `/stories/` listing, or require a separate explicit "feature in listing" toggle? (Leaning: separate toggle, default off, to avoid surprise public listing.)
- Word-frequency block for text questions — in scope as a future block type or never? (Out of scope here.)
- Per-page custom OG cover image vs reusing survey/Story cover — defer to tasks; minimal version derives OG image from the first map/chart block or a default.
