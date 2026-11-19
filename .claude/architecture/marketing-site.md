# Marketing site: vendor facts, category landings, blog, stories, topics, Russian homepage

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Vendor facts on comparison pages (`survey/vendors.py`, change `market-guide-landscape-hub`, #259)**:
every claim the marketing site makes about another vendor is a `Fact(text, source, verified)` in
ONE registry — the public `https://` page it was read from and the ISO date — grouped into
`CATEGORIES` and `CRITERIA`. The market guide `/participatory-mapping-tools/` (the hub above the
`/alternatives/` pages; `/alternatives/` 301s to it) renders vendors × criteria from it, and the
three `/alternatives/` pages render criteria × (Mapsurvey, vendor) through
`partials/_vendor_vs_table.html`, so one correction reaches every page. **Never hand-write a
competitor cell in a template**; a fact the page does not state is `Fact("Not published", <page
read>, <date>)`. No price figure for any vendor but Mapsurvey (owner rule 2026-10-06): the model,
the trial and where a rate is listed; `test_no_competitor_price_figure_on_any_landing` scans
every `Fact.text` and the rendered hub. Import-time `_validate()` and `VendorRegistryTest` refuse
a fact without a source or with a bad date. The five category pages (#251/#252) still carry
hand-written tables; moving them onto the registry is the follow-up after #253. Mapsurvey's own
hosting fact is the United States (Render, Oregon) — the "EU-hosted / Frankfurt" wording that
survived on the Maptionnaire page until this change must not come back.

**Category landings (`/community-engagement-platform/`, `/civic-engagement/`,
`/public-consultation-software/`, `/participatory-budgeting/`; change `seo-landings-rewrite`, #251)**:
one section order on all four (hero → definition → four screenshot steps → feature grid → comparison
table vs two incumbents + "when they fit better" → use cases → pricing → siblings → From the field →
FAQ), styled from the "Category landings" block of `landing.css`, not per-template `<style>`. The Pro
price ($49 a month / $490 a year per workspace) lives in `partials/_landing_pricing.html` and
NOWHERE else on the site, including meta descriptions (`SeoCategoryLandingContractTest` fails if a
template names it): taking the price off the site is one edit. `partials/_landing_siblings.html`
links the four pages to each other (`current`, `audience`). Every comparison cell comes from the
vendor's published pages, dated in the note under the table; "not published" is a valid cell, and
the tables follow the vendors' pages over our older dossiers (Go Vocal draws lines and polygons and
has an AGPL Free Edition; Social Pinpoint's Social Map exports GeoJSON). No marketing page may claim
EU hosting: the hosted service is in the United States, self-hosting is the EU-residency answer.
Rewriting a landing means bumping its `lastmod` in `seo_landings.py` and rewriting its FAQ for the
variant queries Search Console shows it for (`googlesearchconsole_search_analytics_by_query_page`
in PostHog).

**Blog and public changelog (change `public-blog-and-changelog`, #647)**: `/blog/` is ONE feed of
published customer stories (`Story` rows, still at `/stories/<slug>/`) and **articles**, which are
FILES — `survey/blog/<YYYY-MM-DD>-<slug>.html`, a `---` header (`title`, `kind: feature|idea`,
`summary`; optional `cover`/`cover_alt`, `author`, `topics`, `changelog`, `updated`, `draft`) and an
HTML body whose pictures are `{static:img/blog/<slug>/…}` tokens. An article ships in the PR of the
feature it describes, so a merge publishes it — never put articles on `Story` (that path needs a
production `seed_story` and the customer's consent); format and rules in `survey/blog/README.md`,
loader `survey/blog.py` (`feed_items`, `article_map`), views `survey/blog_views.py`. Articles are for
the MOST important changes and are not a copy of the changelog entry; the entry ids named in an
article's `changelog` header get "Read the article" on `/changelog/` and `/editor/whats-new/`.
`/changelog/` renders the same `survey/changelog/` entries publicly (anchors = entry ids, no editor
links, no hero chips). RSS: `/blog/feed.xml`, `/changelog/feed.xml` (absolute links from
`public_base_url`). `draft: true` = staff-only + `noindex`, off the feed, RSS and sitemap.
`BlogArticlesTest.test_shipped_articles_load` fails CI on a malformed file.

**Customer stories (`Story`, `StoryImage`; change `customer-stories-showcase`)**: the homepage
"From the field" carousel and `/stories/<slug>/` are DB rows, but the REPO is the source:
`survey/story_data/<slug>/` holds `story.json` (fields, cover/card/logo file names, `images`
key→file), `body.html` and `images/`; `python manage.py seed_story <slug> [--draft]` installs or
refreshes the row (idempotent by slug, keeps id and first `published_date`, uploads pictures to
the public media tier). Body pictures are `{img:<key>}` tokens resolved by
`survey/stories.py::render_body` against the story's `StoryImage`s, so one body works on
production, previews and laptops whose media prefixes differ. The body is staff-authored HTML
rendered `|safe` — not creator input. A re-run of the command overwrites admin text edits.
**Publishing is a separate step (change `story-draft-publishing`)**: `seed_story <slug>` installs
a NEW story as a draft and a re-run keeps the current state (`--publish` / `--draft` force it), so
prepared stories can sit on production unpublished. The repo is public: a story whose customer
has not approved it yet is NOT committed; copy its directory to the server and run
`seed_story <slug> --from <dir>`. Staff open a draft at its normal URL (draft
banner, `noindex`); everyone else gets 404, and drafts stay off the landing, `/stories/` and the
sitemap. The customer's written OK on text and pictures (each `story_data` dir carries a
`CREDITS.md`) → the admin's "Publish" action or the list checkbox. A story body may carry the
**Lessons learned** callout (`<aside class="sd-lessons">`, change `story-lessons-learned`): one
look in every story, each lesson with an "In Mapsurvey" line tagged Available / Built for … /
Not yet; `Story.has_lessons` puts a badge on the card. The whole path from consent to `seed_story` — prod-DB facts, heat maps and phone
screenshots taken on a LOCAL import of the survey (opening the live one creates an `external`
session in the customer's data), the approval HTML (`scripts/story_approval_html.py`) and cover
letter — is the `customer-story` skill (`.claude/skills/customer-story/SKILL.md`);
`StoryDataDirectoriesTest` seeds every `story_data` dir.

**Story topics (change `story-topics`, issue #250)**: `Story.topics` is a list of slugs from the
ONE registry `survey/topics.py` (`Topic(slug, label, landing_key)`); `seed_story` and the admin
form refuse a slug that is not there, so a tag always means the same page. A topic whose
`landing_key` names an entry of `SEO_LANDINGS` links both ways: the story page shows it as a chip
linking to the landing, and `render_seo_landing` puts the published stories carrying it into the
landing's "From the field" block (`partials/_topic_stories.html`, included before the FAQ on all
12 landings; nothing renders for the alternatives pages, which own no topic). A topic without a
landing is a plain chip and a candidate page for epic #257. `/stories/?topic=<slug>` filters the
index; its canonical stays `/stories/`. Production stories seeded from the ops repo are tagged in
the admin. A new landing page gets its topic by setting `landing_key`, never by a second list.

**Russian homepage and hreflang (change `ru-landing-hreflang`, issue #248)**: `/ru/` is the
homepage rendered by `views.index_ru` under `lang_override('ru')` — one route, NOT `i18n_patterns`,
and `ru` stays out of `LANGUAGES` (the creator catalog is incomplete). `home_path` and `page_lang`
in the context tell `base_landing.html` which twin it is rendering: brand/anchors stay on `/ru/`, the
EN/RU switcher shows only on the pair, `<html lang>` comes from `page_lang` (there is no i18n context
processor, so `LANGUAGE_CODE` is empty in templates). Every `base_landing` page emits `hreflang`
`en` + `x-default` for itself; `landing.html` overrides that with the `en`/`ru`/`x-default` triple,
which the sitemap repeats as `xhtml:link`. `RussianLandingHreflangTest` fails when a homepage msgid
has no compiled `ru` translation — a new `{% trans %}` on the homepage needs its Russian in the same
PR. Sitemap/robots URLs come from `_public_base_url` (`X-Forwarded-Proto`, else `SITE_URL`'s scheme
on its host), because `request.scheme` is `http` behind the proxy.
