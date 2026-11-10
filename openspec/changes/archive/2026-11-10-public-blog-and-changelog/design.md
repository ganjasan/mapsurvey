## Context

Three kinds of public writing exist or are wanted: customer stories (`Story` rows seeded from
`survey/story_data/`, gated by the customer's written OK), changelog entries (files in
`survey/changelog/`, shipped with the feature, today visible only in the editor), and longer
articles about a feature or an idea (nothing yet). The owner's decision (2026-11-10): one blog
that holds the stories and separate articles about the most important features — not a copy of
the changelog — and a public changelog, all in one PR.

The stale branch `feature/stories-kinds` (#240) tried to put articles on the story engine with a
`Story.kind`. That branch is the starting point for this design, not its code.

## Goals / Non-Goals

**Goals:** one feed at `/blog/`; articles that publish by merging, with the feature; the
changelog crawlable at `/changelog/`; RSS; articles linked both ways with changelog entries.

**Non-Goals:** comments, subscriptions by email, authors as a model, tags beyond the existing
topic registry, guides (#255 — a third `kind` later), translations of articles, moving stories
off `/stories/<slug>/`, an editor UI for writing posts.

## Decisions

**1. Articles are files, not `Story` rows.** A story needs the DB because its pictures and
approval live outside the public repo until the customer agrees; an article needs neither. As a
file it ships in the feature's PR, publishes on merge (prod in minutes), is reviewed in the diff,
and cannot announce something that is not deployed — the changelog's rule. A `Story.kind` would
add a migration, a `seed_story` run on production per article and a media upload per picture.
*Rejected*: Story.kind (#240's plan); a Starlight blog on help.mapsurvey.org (splits authority
off the main domain, and the help site is documentation).

**2. File format mirrors the changelog.** `survey/blog/<YYYY-MM-DD>-<slug>.html`, a `---` header
of `key: value` lines, then HTML. The slug is the filename without the date and is the URL
(`/blog/<slug>/`); the date is the publication day. Keys: `title`, `kind` (`feature` | `idea`),
`summary` (card lead and meta description) required; `cover` + `cover_alt` (static path under
`survey/assets/`), `author` (default "Mapsurvey"), `topics` (comma list, validated by
`topics.validate_slugs`), `changelog` (comma list of entry ids, each must exist), `updated`
(ISO date), `draft` (`true`). Body pictures are `{static:img/blog/<file>}` tokens resolved with
`staticfiles_storage.url`, so the manifest hashes apply. `survey/blog.py` parses, validates and
caches once per process (`lru_cache`), raising `BlogError` naming the file; a test loads the
whole directory so a bad file fails CI.

**3. One feed, two sources, one item shape.** `blog.feed_items(include_drafts=False)` returns
`FeedItem(kind, title, summary, date, url, picture_url, picture_alt, label, source)` built from
published `Story` rows (`kind='story'`) and published articles, newest first by date (stories by
`published_date`). The index renders story items with the existing `_story_card.html` (so the
card looks the same as on `/stories/`) and article items with `_post_card.html` built on the same
`story-card` classes. Chips `?kind=stories|features|ideas` are plain links; a kind with no items
is not offered; the canonical is `/blog/` for every filter. `/stories/` stays as the customer
stories view with its topic filter — it is an indexed page and stories link back to it.

**4. Drafts.** A draft article renders for staff with a banner and `noindex`, 404 for everyone
else, and is absent from the feed, RSS and sitemap — the story-draft rule.

**5. Public changelog = same entries, public template.** `/changelog/` lists every entry newest
first with `id="<entry id>"` anchors, the image, the body, the New/Fixed tag. No "Open" links
(they point into the editor) and no hero chips. An entry named by an article's `changelog`
header shows "Read the article"; `blog.article_for_entry(id)` is the reverse map, also used by
`/editor/whats-new/`. Hero-only header keys are ignored here.

**6. RSS via `django.contrib.syndication.views.Feed`** (stdlib of Django, no `INSTALLED_APPS`
change): `/blog/feed.xml` (articles + stories, 20 newest), `/changelog/feed.xml` (30 newest
entries, link to the anchor). Absolute links use `_public_base_url`-equivalent `SITE_URL` logic
through the request (`request.build_absolute_uri` behind the proxy gives `http`; use
`settings.SITE_URL` for `link`s, as the sitemap does with its base).

**7. Chrome.** Nav gets "Blog" (after Pricing/Services, before Trust); footer Resources gets
"Blog" and "Changelog" above "Customer stories". "Blog" and "Changelog" need `ru` entries —
the homepage catalog test reads every msgid of the homepage templates.

## Risks / Trade-offs

- [Two engines behind one feed] → one `FeedItem` shape and one sort; the story card is reused,
  not copied.
- [Static images grow the repo] → PNG/JPG under ~300 KB, the changelog already does this.
- [Fixed-entry candour on a public page (e.g. lost answers in October)] → the entries are in the
  public repo already; the page shows what the repo shows.
- [`kind` vocabulary may grow (guides)] → `KINDS` is one tuple in `blog.py`; the chip list
  derives from it.
