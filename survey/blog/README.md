# Blog articles

One file per article, shipped in the same PR as the feature it describes (or on its own for an
idea). Merging publishes it at `https://mapsurvey.org/blog/<slug>/`; `/blog/` lists it next to the
customer stories. Loader and rules: `survey/blog.py`. Change `public-blog-and-changelog` (#647).

Articles are for the **most important** changes — a new question type, a new module, a workflow
that changes how people run a consultation. Everything else stays a changelog entry
(`survey/changelog/`). An article is not a copy of its entry: the entry says what changed in two
paragraphs, the article explains the problem, how it works, what you get and where it fits.

## File

`YYYY-MM-DD-slug.html` — the date is the publication day, the slug is the URL. Both are
permanent once published: a renamed slug is a broken link.

```
---
title: Budget questions: ask what people would give up
kind: feature
summary: One or two sentences. The card lead, the meta description and the RSS text.
cover: img/blog/budget-questions/park.jpg
cover_alt: What the cover shows, for screen readers
author: Mapsurvey
topics: participatory-budgeting, public-consultation
changelog: 2026-11-10-budget-questions
updated: 2026-11-20
draft: true
---
<p>Body in HTML: p, h2, h3, ul/ol, img, a, code, blockquote.</p>
<p><img src="{static:img/blog/budget-questions/split.jpg}" alt="..." width="560"></p>
```

- `title`, `kind` (`feature` or `idea`), `summary` — required.
- `cover` + `cover_alt` — optional static path under `survey/assets/` (put pictures in
  `survey/assets/img/blog/<slug>/`, JPEG, under ~300 KB each). A cover needs alt text.
- `author` — defaults to "Mapsurvey".
- `topics` — slugs from `survey/topics.py`; each renders as a chip linking to its landing page.
- `changelog` — ids of the changelog entries this article expands. Each entry then shows
  "Read the article" on `/changelog/` and in the editor's "What's new". An unknown id fails CI.
- `updated` — ISO date of a substantive revision (shown on the page, used in the sitemap).
- `draft: true` — only staff can open it (with `noindex`); it is on no list, feed or sitemap.
  Remove the line to publish.

Pictures in the body are `{static:<path>}` tokens, never hard-coded `/static/...` URLs: the
storage adds content hashes to file names.

A malformed file fails `BlogArticlesTest.test_shipped_articles_load`. The text itself has no
tests; it is reviewed in the PR. The site rules for marketing text apply: no competitor prices,
no EU-hosting claims, facts you can point to.
