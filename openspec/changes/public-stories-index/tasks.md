## 1. Structured-data helper

- [x] 1.1 Add `build_story_collection_jsonld(request, stories)` to `survey/seo_landings.py` returning a `CollectionPage` with an `ItemList` `mainEntity` (position/url/name per story), as a `json.dumps` string. Reuse `build_breadcrumb_jsonld` for breadcrumbs.

## 2. Stories index view + template

- [x] 2.1 Add `stories_index(request)` view in `survey/views.py`: query `Story.objects.filter(is_published=True).order_by('-published_date')`, build breadcrumb (`Home › Stories`) + collection JSON-LD, render `stories_index.html`.
- [x] 2.2 Add `path('stories/', views.stories_index, name='stories_index')` to `survey/urls.py` (above or below the `stories/<slug>/` route — both resolve unambiguously).
- [x] 2.3 Create `survey/templates/partials/_story_card.html` — one card (cover image or typed placeholder, `story_type` badge, title, date, link to `stories/<slug>/`).
- [x] 2.4 Create `survey/templates/stories_index.html` extending `base_landing.html`: SEO blocks (`title`, `meta_description`, `canonical_url`, `og_url`), `structured_data` block including breadcrumb + collection JSON-LD, a card grid looping `_story_card.html`, and an empty state.

## 3. Story detail SEO

- [x] 3.1 In `story_detail`, compute `canonical`, `meta_description` (`strip_tags(body)` truncated ~155 chars, title fallback), and breadcrumb JSON-LD (`Home › Stories › <title>`); pass to context.
- [x] 3.2 Update `story_detail.html` to fill `meta_description`/`canonical_url`/`og_url` blocks and add the `structured_data` block with the breadcrumb.

## 4. Sitemap + footer

- [x] 4.1 In `sitemap_xml`, append a `/stories/` entry and loop published stories emitting `stories/<slug>/` with `<lastmod>` from `published_date` when set.
- [x] 4.2 Add a "Stories" link (`href="/stories/"`) to the `base_landing.html` footer (Product column).

## 5. CSS

- [x] 5.1 Add `.story-card` grid + card styles to `survey/assets/css/landing.css` (reuse existing tokens; typed-placeholder for cards without a cover image); run `collectstatic`.

## 6. Tests (`survey/tests.py`)

- [x] 6.1 `StoriesIndexViewTest`: `/stories/` returns 200 and lists published (not draft) stories with detail links; empty state returns 200.
- [x] 6.2 Assert index `BreadcrumbList` + `CollectionPage`/`ItemList` JSON-LD present, valid, and item count matches published stories.
- [x] 6.3 Assert detail page has self-canonical, non-empty meta description, and a 3-item `Home › Stories › <title>` breadcrumb.
- [x] 6.4 Assert sitemap contains `/stories/` and a published story URL, and excludes a draft story's URL; footer on a landing links to `/stories/`.

## 7. Verify

- [x] 7.1 Run `./run_tests.sh survey`; fix failures. Spot-check `/stories/` JSON-LD validity.
