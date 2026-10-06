## Context

`Story` rows come from `survey/story_data/<slug>/story.json` through `seed_story` (customer stories whose consent is pending live in the ops repo and are seeded with `--from`). The 12 SEO landing pages are registered in `survey/seo_landings.py` and all rendered by `render_seo_landing`, which is the one place that builds their context. Every landing template ends with `{% include "partials/_faq_section.html" %}`.

## Goals / Non-Goals

**Goals:** a story links to the landing page of each topic it illustrates; a landing page lists the stories that illustrate it; the vocabulary is controlled so a tag always means the same page.

**Non-Goals:** free-form tags; topic pages at their own URLs; changing the homepage carousel; the `platform` / `guide` story kinds (#240) — the field applies to them unchanged.

## Decisions

**A registry, not free text.** `Topic(slug, label, landing_key=None)` in `survey/topics.py`; `TOPICS` is the ordered tuple and `landing_key` is unique where set. A tag that is not a registry slug fails `seed_story` loudly and the admin field validates the same way, so the vocabulary cannot drift into "community-engagement" vs "community_engagement". Topics carry their landing key rather than landings carrying topics, because topics outnumber landings and the gap list ("topics with stories but no page") is what drives the rest of epic #257.

**`topics` is a JSONField list of slugs**, like `facts`, not an M2M to a model. The registry is code; a table would need seeding and admin plumbing for a dozen rows that change in PRs anyway. The lookup "stories with topic X" is `topics__contains=[slug]`, which Postgres answers from the jsonb column; four to forty stories do not need an index.

**Landing block through `render_seo_landing`.** The helper already builds every landing context; it adds `topic_stories` (published, showcase order, `topics__contains` the landing's topic) and `topic` for the heading. A new partial `partials/_topic_stories.html` renders the block with `_story_card.html` and is included once per landing template, before the FAQ include, so the block sits where the page's proof belongs and the FAQ stays last for the FAQPage structured data. Alternatives pages have no topic and render nothing.

**Chips link only where a page exists.** A chip for a topic without a landing is plain text: a link to `/stories/?topic=…` would be a filtered copy of the index with the same canonical, worth nothing to a crawler and confusing to a reader.

**Index filter is a query string, canonical unchanged.** `?topic=<slug>` filters the grid and marks the active chip; an unknown slug shows the full grid. The canonical and the CollectionPage JSON-LD stay those of `/stories/`, so the filter cannot create duplicate indexable URLs.

**Tagging the ops-repo stories.** Their `story.json` lives in `../Mapsurvey-ops`; the file edit is part of this change, the production rows are tagged in the admin after deploy (re-seeding over SSH is the alternative and is not required).

## Risks / Trade-offs

- A story tagged with a topic that later gets a landing page links to nothing until the registry row is updated. Accepted: it is one line in `topics.py`, and the "topics without a landing" set is what the epic works through.
- `seo_landings.py` is also edited on the `feature/stories-kinds` branch (#240). The edits do not overlap in function; merge order does not matter.

## Migration Plan

`0092_story_topics` adds the JSONField with `default=list`; no data migration. Rollback is a revert; the column stays and is ignored.
