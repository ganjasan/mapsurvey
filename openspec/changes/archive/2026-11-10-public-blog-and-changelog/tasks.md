## 1. Article engine

- [x] 1.1 `survey/blog.py`: parse/validate `survey/blog/*.html` (header keys, kinds, topics, changelog ids, `{static:}` tokens), cached loader, `published()`, `by_slug()`, `article_for_entry()`, `feed_items()` over stories + articles
- [x] 1.2 `survey/blog/README.md`: the file format and the "ship with the feature" rule

## 2. Pages

- [x] 2.1 `survey/blog_views.py`: `blog_index` (kind chips), `blog_post` (drafts staff-only, JSON-LD), `changelog_public`, RSS feeds
- [x] 2.2 Templates `blog_index.html`, `blog_post.html`, `changelog_public.html`, `partials/_post_card.html`; styles in `landing.css`
- [x] 2.3 URLs, sitemap entries, nav "Blog", footer "Blog"/"Changelog", `ru` catalog entries
- [x] 2.4 "Read the article" on `/editor/whats-new/`

## 3. Content

- [x] 3.1 First feature article: budget questions (#447), with screenshots

## 4. Tests and docs

- [x] 4.1 `survey/tests/test_public_blog.py`: loader refusals + shipped directory, feed order and filter, draft 404, sitemap, RSS
- [x] 4.2 `test_in_app_changelog.py`: public page, article link on both pages
- [x] 4.3 CLAUDE.md paragraph; run the touched modules
