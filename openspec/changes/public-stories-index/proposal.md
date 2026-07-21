## Why

`robots.txt` allows `/stories/` and the sitemap work assumes a stories hub, but no index page exists — only `stories/<slug>/` detail pages. `/stories/` currently 404s, so the allow-rule points at nothing, individual stories are undiscoverable (no internal link path, not in the sitemap), and the "public results showcase gallery + SEO" growth item (organic acquisition via indexable results/story pages) has no landing surface. This change adds the missing hub and makes stories crawlable.

## What Changes

- Add a **stories index** at `/stories/` (`stories_index` view + template) listing all published stories as a card grid, newest first, with a tasteful empty state.
- Add a reusable **story-card partial** and card CSS, so the index and any future placement share one card.
- **SEO for the hub**: per-page `title`/`meta_description`/`canonical`, a `BreadcrumbList` (`Home › Stories`), and a `CollectionPage`/`ItemList` JSON-LD of the listed stories.
- **SEO for detail pages**: give `story_detail.html` a `canonical`, a `meta_description` (derived from the story), and a `BreadcrumbList` (`Home › Stories › <title>`) — currently it has none.
- **Discoverability**: include `/stories/` and every published story URL in `sitemap.xml`; add a "Stories" link to the landing footer.
- Add tests: index renders published (not draft) stories, empty state, `/stories/` returns 200, breadcrumb/collection JSON-LD valid, sitemap contains the hub and published stories, detail-page canonical/breadcrumb present.

No model or migration changes; no breaking changes.

## Capabilities

### New Capabilities
<!-- None new; this extends the existing public-stories capability. -->

### Modified Capabilities
- `public-stories`: ADD a stories index page at `/stories/`, story-detail SEO metadata (canonical, meta description, breadcrumb), and sitemap inclusion of the hub and published story pages. Existing story model / detail-view / admin requirements are unchanged.

## Impact

- **Views / Python**: `survey/views.py` — new `stories_index`; `sitemap_xml` gains `/stories/` + published story URLs; `story_detail` context gains SEO fields (canonical/description/breadcrumb).
- **URLs**: `survey/urls.py` — new `path('stories/', ...)` (the `stories/<slug>/` route is unaffected; `stories/` cannot match a slug route).
- **Templates**: new `survey/templates/stories_index.html` + `partials/_story_card.html`; `story_detail.html` gains SEO blocks + breadcrumb; `base_landing.html` footer gains a Stories link.
- **CSS**: `survey/assets/css/landing.css` — `.story-card` grid styles (run `collectstatic`).
- **Tests**: `survey/tests.py` — new index/SEO test class.
- **No** model/migration/DB impact; **no** new dependencies.
