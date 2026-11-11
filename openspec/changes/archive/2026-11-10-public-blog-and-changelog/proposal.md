## Why

We ship two or three changes a week and nobody outside the editor sees it: the in-app changelog
is behind login, customer stories sit alone at `/stories/`, and there is no place for a longer
piece about a feature or an idea. Search engines and AI assistants cite only what they can crawl
on mapsurvey.org. Senf.app runs a `/blog/` with a founder byline; we have more product news than
they do and publish none of it (#647, supersedes #240).

## What Changes

- **`/blog/`** — one public feed of customer stories (the existing `Story` rows, URLs unchanged at
  `/stories/<slug>/`) and articles. Kind chips: All · Customer stories · Features · Ideas
  (`?kind=`), canonical always `/blog/`.
- **Articles** — files in the repo, `survey/blog/<YYYY-MM-DD>-<slug>.html`: a `---` header
  (`title`, `kind: feature|idea`, `summary`, optional `cover`, `cover_alt`, `author`, `topics`,
  `changelog`, `updated`, `draft`) and an HTML body whose pictures come from static files. An
  article ships in the PR of the feature it describes, so publishing is a merge, the same rule as
  changelog entries. `draft: true` = staff-only with `noindex`, off every list. Page
  `/blog/<slug>/` with `BlogPosting` JSON-LD. A malformed file fails CI.
- **`/changelog/`** — the public changelog, rendered from the same `survey/changelog/*.html`
  entries as the in-app "What's new", newest first, each with an anchor. An entry that an article
  names in its `changelog` header links to that article — here and on `/editor/whats-new/`.
- **RSS** — `/blog/feed.xml` and `/changelog/feed.xml` (Django's syndication framework, no new
  dependency), advertised in the pages' `<head>`.
- **Discovery** — sitemap entries for `/blog/`, `/changelog/` and every published article; "Blog"
  in the marketing nav; "Blog" and "Changelog" in the footer's Resources column.
- **First feature article**, for the budget questions shipped in #447.

## Capabilities

### New Capabilities
- `public-blog`: the article files and their loader, the `/blog/` feed over stories and articles,
  the article page, drafts, the blog RSS feed, sitemap and chrome links.

### Modified Capabilities
- `in-app-changelog`: the entries are also published at `/changelog/` with an RSS feed, and an
  entry links to the article that expands it (public page and `/editor/whats-new/`).

## Impact

- New: `survey/blog.py` (loader), `survey/blog/` (articles + README), `survey/blog_views.py`
  (feed, article, changelog page, RSS), templates `blog_index.html`, `blog_post.html`,
  `changelog_public.html`, `partials/_post_card.html`, images under `survey/assets/img/blog/`.
- Changed: `survey/urls.py`, `views.sitemap_xml`, `base_landing.html` (nav, footer),
  `editor/whats_new.html` + `editor_views.whats_new_page` (article link), `landing.css`
  (feed chips/post card reuse the story styles), `ru` catalog for the two chrome strings.
- `Story` is unchanged: no migration, no change to `seed_story` or the consent path.
- Tests: `survey/tests/test_public_blog.py` (new), `test_in_app_changelog.py`.
