## Context

`Story` (`survey/models.py`) has `title`, `slug`, `body`, `cover_image`, `story_type` (map/open-data/results/article), optional `survey` FK, `is_published`, `published_date`. `story_detail` renders published stories at `stories/<slug>/`; the root view passes a `stories` queryset to `landing.html` but the current marketing `landing.html` no longer renders a stories section (pre-existing drift, out of scope). `base_landing.html` already provides `structured_data`, `canonical_url`, `meta_description` blocks (from the landing-seo-structured-data change) and a `build_breadcrumb_jsonld` helper in `survey/seo_landings.py`.

## Goals / Non-Goals

**Goals:**
- A crawlable `/stories/` hub that lists published stories and links to each.
- Reuse the existing breadcrumb helper and `structured_data` block for consistency with the SEO landings.
- Make detail pages self-canonical and breadcrumbed; add hub + published stories to the sitemap.

**Non-Goals:**
- No editing UI (stories are managed in Django admin, unchanged).
- No re-adding a stories section to the marketing homepage (separate concern).
- No pagination (story volume is low; revisit if it grows).
- No new model fields, no migration.

## Decisions

**D1 — Reuse `seo_landings.build_breadcrumb_jsonld`.** Rather than a second breadcrumb builder, import the existing helper and pass `Crumb` lists. The hub uses `[Home, Stories]`; a detail page uses `[Home, Stories, <title>]`. Keeps one JSON-LD code path and one escaping guarantee.

**D2 — `CollectionPage` + `ItemList` for the hub.** Emit a `CollectionPage` JSON-LD whose `mainEntity` is an `ItemList` of the listed stories (position + url + name). This is the schema.org-correct shape for a listing page and mirrors the FAQPage/Breadcrumb approach: built in Python via `json.dumps`, passed to the template as a safe string. Add a small `build_story_collection_jsonld(request, stories)` helper next to the others in `seo_landings.py` (it is SEO structured-data, same module).

**D3 — Story card as a partial.** `partials/_story_card.html` renders one card (cover image or a typed placeholder, title, `story_type` badge, date, link to detail). The index loops it. A card links to `stories/<slug>/`.

**D4 — Sitemap: hub is static, stories are queried.** In `sitemap_xml`, add one `/stories/` entry and loop `Story.objects.filter(is_published=True)` emitting `stories/<slug>/` with `lastmod` from `published_date` when present. Story detail is not in the SEO-landing registry (different content type), so it is added directly in the view — consistent with how per-survey URLs are already appended there.

**D5 — Detail-page SEO via context, not template literals.** `story_detail` computes `canonical`, `meta_description` (first ~155 chars of `body`, tags stripped, or the title as fallback), and `breadcrumb_jsonld`, passing them to the template which fills the base blocks. Keeps escaping/JSON in Python.

**D6 — Empty state.** When no stories are published, `/stories/` still returns 200 with a short "no stories yet" message and a CTA back to the product — a valid hub page beats a 404 the robots file points at. The hub stays in the sitemap regardless; individual story URLs only appear when published.

## Risks / Trade-offs

- **[Thin/empty hub looks low-value to crawlers]** → acceptable: the page is a legitimate hub, and it only lists real content; if it stays empty long-term that is a content problem, not a code one. Documented in the outreach checklist.
- **[Duplicate content between story body and meta_description]** → description is a truncated plain-text excerpt, standard practice; canonical points to self.
- **[`body` may contain HTML]** → meta_description strips tags (`django.utils.html.strip_tags`) before truncation; detail body already renders with `|safe` as today (unchanged).
- **[Breadcrumb name for long titles]** → schema allows full title; no truncation needed in JSON-LD (only the visible `<meta>` description is truncated).

## Migration Plan

Additive, no DB. Deploy = view/template/CSS; run `collectstatic`. Rollback = revert commit. After deploy, resubmit the sitemap in Search Console so the new hub + story URLs are discovered (manual, tracked in the outreach checklist).

## Open Questions

- None blocking. Pre-existing drift (landing.html no longer shows a stories section though the public-stories spec still requires it) is noted but left for a separate cleanup.
