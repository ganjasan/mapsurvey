# Writing for the Mapsurvey help centre

This folder is the help site at <https://help.mapsurvey.org> (Astro + Starlight). It is a
static site built by its own Render service from `help/`; a pull request that touches this
folder gets a preview, and a feature's guide ships in the same PR as the feature.

```bash
cd help
npm ci
npm run dev        # http://localhost:4321
npm run build      # fails on a broken internal link
```

## Where a page goes

The sections split content by what the reader is doing, not by topic (Diátaxis). Pick the
section first; the page shape follows from it.

| Reader is… | Section | Folder | Page shape |
|---|---|---|---|
| learning by doing, first time | Start here | `start-here/` | Tutorial: one path, numbered pages |
| doing a task they already understand | How-to guides | `how-to/` | How-to: one task, numbered steps |
| checking a fact | Reference | `reference/` | Reference: tables and definitions, no steps |
| stuck on an error | Troubleshooting | `troubleshooting/` | Symptom → why → what to do |
| trying to understand the practice | Learn | `learn/` | Essay with sources |
| looking for an example like theirs | Use cases | `use-cases/` | What was asked, how it was built, what came back |
| asking a quick question | FAQ | `faq.md` | Question in the asker's words, ≤ 3 sentences, link out |

One page, one shape. A how-to that starts explaining the theory becomes two pages: the how-to
and a Learn essay it links to.

## Page shapes

**How-to** — title starts with the verb, sentence case: "Add a reference layer", not
"Reference layers" or "Adding Reference Layers". Then:

```md
---
title: Add a reference layer
description: Show respondents a GeoJSON layer (boundaries, sites, routes) beneath the map.
---

One line on what the reader ends up with.

## Before you start          <!-- only if something is required -->

## Steps
1. One action per step. Put the condition first: "If the file is larger than 10 MB, split it."
2. Screenshot *after* the step it illustrates, never before.

## Result
What the reader should now see.

## Related
- [Style a layer by property](/how-to/style-a-layer/)
```

**Reference** — complete and neutral. Tables for anything with more than three attributes.
No instructions; link to the how-to instead.

**Troubleshooting** — the title is the message the product shows ("Autosave failed"), so a
reader can search for what they saw. Sections: `## Why it happens`, `## What to do`
(numbered), `## If it keeps happening` (what to send support). The slug is referenced from
the product's error states (`survey/help_links.py`); renaming it needs a redirect.

**Learn** — an essay, headings every few paragraphs, sources cited by name and linked
(publisher's page, never a copied PDF). End with the how-to that applies. Paraphrase private
research notes; never paste them.

**FAQ** — add a question only when someone asked it: support chat, email, a demo request,
or a landing-page FAQ. Put the source in an HTML comment above the question. Answer in at
most three sentences and link to the page that answers in full. Keep the groups; add the
question to the jump-link list at the top.

## Style

- Sentence case for every title and heading. Present tense, active voice: "The export
  contains…", not "The export will contain…".
- Address the reader as "you". Mapsurvey is "Mapsurvey", never "the system" or "the app".
- UI labels in **bold** exactly as shown: **Publish**, **Share**, **Responses › Map**.
- Numbered lists for sequences, bullets for sets. Never a step without a verb.
- No "simply", "just", "easy". If it were, the page would not exist.
- Dates and units spelled out: "10 MB", "within a day".

## Screenshots

- Path: `src/assets/<section>/<slug>-<n>.png`, referenced as `![alt](../../assets/...)` so
  Astro optimises them. Alt text says what the picture shows, not "screenshot".
- 1440 px wide window, light theme, a demo survey (never a customer's), browser chrome
  cropped. Keep the cursor out of the frame; use a 2 px teal outline (`#0FA58E`) to point.
- Retake when the UI changes; a stale screenshot is worse than none.

## Frontmatter

```yaml
title: Add a reference layer          # required
description: One sentence for search results and link cards.   # required
sidebar:
  order: 20                           # optional; otherwise alphabetical
draft: true                           # keeps the page out of the build
```

The sidebar is generated from the folders, so nothing in `astro.config.mjs` changes when
you add a page.

## Moving or renaming a page

Slugs are identifiers: the product links to them (`survey/help_links.py`, with a test that
every path exists) and so do people's bookmarks. When a slug changes, add
`'/old/path/': '/new/path/'` to `redirects` in `astro.config.mjs` in the same commit.

## Maintenance rule

A closed support conversation ends in one of two edits: a new FAQ entry (with its source
comment) or a fix to the guide that should have answered it. Every quarter, sort pages by the
lowest "Was this helpful?" ratio in PostHog (`help_feedback`) and rewrite the bottom ones;
read `help_search` queries with zero results for pages that are missing.
