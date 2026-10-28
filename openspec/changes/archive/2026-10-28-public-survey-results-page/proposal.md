## Why

Survey creators currently have a rich analytics dashboard, but it is editor-only. The only way to surface results publicly is to hand-author a `Story` in Django admin, disconnected from live data. Creators want to publicly demonstrate aggregated results to: close the feedback loop with participants ("your voice counted"), attract new respondents via social proof, report outcomes to stakeholders, and showcase the Mapsurvey platform. A single curated, shareable public results page serves all four motivations.

## What Changes

- Add a **public results page** per survey, configured by the creator and served at a short public URL (`/r/<slug>/`).
- Creator curates which questions appear, in what order, and how each is visualized (drag-and-drop blocks), plus an optional multilingual intro text.
- **Hybrid live/freeze model**: blocks render live aggregates through the existing `SurveyAnalyticsService`, or the creator can freeze a snapshot (stakeholder-grade, stable numbers). A toggle returns the page to live or refreshes the snapshot.
- **Data granularity**: aggregates (charts, counts, heatmaps) plus anonymous geo features (points/lines/polygons) with creator-selected popup label fields. **Individual text answers are never published.**
- **Access control**: a `Public` / `Unlisted` visibility toggle. Public pages are indexable and may appear in the existing `/stories/` listing; Unlisted pages are `noindex` and reachable only by direct link.
- **Privacy guards**: only clean sessions feed the page (deleted/invalid sessions excluded, reusing dashboard filters); k-anonymity threshold (default K=3) masks small buckets as "<3"; record-level identifiers (session id, IP, UTM, timestamps) are never exposed.
- **Engagement affordances**: optional response counter (social proof) and a "Take the survey" CTA shown while the survey is open. A "Made with Mapsurvey" footer on every page.
- New editor tab `/editor/surveys/<uuid>/public-results/` alongside Analytics and Share.

## Capabilities

### New Capabilities
- `public-results-page`: Creator-curated, publicly accessible page of aggregated survey results with hybrid live/frozen data, anonymous geo display, visibility control, privacy guards (clean-session filtering, k-anonymity, no individual texts), and engagement affordances (response counter, participate CTA, platform footer).

### Modified Capabilities
<!-- None: the public-stories listing integration is additive (an optional card), not a requirement-level change to that capability. The analytics service is reused without contract changes. -->

## Impact

- **New model code**: `PublicResultsPage` (1:1 with `SurveyHeader`) and `PublicResultsBlock` in `survey/models.py`; new migration.
- **New views/URLs**: public view at `/r/<slug>/`; editor config views under `/editor/surveys/<uuid>/public-results/`. New top-level `/r/` URL prefix in `survey/urls.py`.
- **Reuse, no contract change**: `SurveyAnalyticsService` (`survey/analytics.py`) for aggregates, geo feature collection, and clean-session filtering.
- **Templates**: new public results template + editor config template (HTMX + SortableJS, matching the WYSIWYG editor); shared block partials reused for live and frozen rendering.
- **SEO**: robots/OG meta on the public page; optional integration with the `/stories/` listing and `robots.txt`/`sitemap.xml`.
- **No breaking changes**: purely additive; default state is unpublished, so existing surveys are unaffected.
