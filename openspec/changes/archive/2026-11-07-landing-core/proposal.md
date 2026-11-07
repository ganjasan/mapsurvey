## Why

An engagement is longer than one survey: a pilot, the main survey, a feedback round, open-house
events, documents. Residents meet it through flyers and QR codes that need one address valid
from the first pilot to the final plan, and today that "front door" is built by hand on the
consultant's or the council's own site. Epic #348 (Vision and Scope in the ops repo,
`requirements/vision/landing-pages.md`) makes it a workspace object in Mapsurvey. This change is
step 1 of 4 (#576): the entity, the block builder and the public page. Documents and map (#577),
results blocks (#578) and event registration (#579) build on it.

## What Changes

- **`Landing`**, a workspace-owned public page: title, summary, cover picture, slug, page
  language, visibility (public / unlisted), draft / published.
- **Linked surveys, many-to-many**: any survey of the same workspace can be linked to any number
  of landings (`LandingSurvey`, canonical survey only). Nothing is linked automatically.
- **Blocks** (`LandingBlock`), an ordered list from a closed set, one column, no styling:
  rich text, image, button, video (YouTube / Vimeo), FAQ, timeline of phases, survey card.
  Every block's data passes one validator, `survey/landings.py::clean_block`; rich text goes
  through `coerce_creator_html`.
- **Workspace pages**: `/org/<slug>/landings/` (list, create) and
  `/org/<slug>/landings/<uuid>/` (the builder: settings, linked surveys, blocks with an
  *Add block* picker, drag to reorder, publish / unpublish, preview). Sidebar entry
  *Landing pages*.
- **Public page** `/p/<slug>/`: hero, anchor navigation from block titles, the blocks, the
  abuse-report footer; sitemap entry when public, `noindex` when unlisted, share link and QR.
  Members preview a draft at the same URL with a banner; everyone else gets the
  `survey_unavailable` 404.
- **Pro**: new feature `landing_pages` (trial allowance: 1 landing created). Creating,
  editing and publishing need it; a landing published while Pro **stays online** after a lapse
  (printed QR codes keep working) but cannot be edited until the workspace is Pro again.
- **Content screening** generalised to a landing: publishing a landing, and saving one that is
  published, runs the same signal table; a hold serves the 404 and mails the moderator.
- Help page, translations in every offered catalog, PostHog events `landing_created`,
  `landing_published`.

## Capabilities

### New Capabilities
- `survey-landings`: the landing entity, linked surveys, block types and their validation,
  the builder pages and roles, the public page and its visibility, the Pro gate and the lapse
  rule, screening of landings.

### Modified Capabilities
- `abuse-review`: a review row names either a survey or a landing; the notice, the review page
  and *Confirm phishing* handle a landing.

## Impact

- Models + migration: `Landing`, `LandingSurvey`, `LandingBlock`; `ContentReview.landing`
  (nullable, survey made nullable, one-of constraint).
- New: `survey/landings.py` (block schema, validation, rendering context), 
  `survey/landing_views.py` (builder) and the public view, templates under
  `survey/templates/landings/`, `survey/assets/js/landing_builder.js`,
  `survey/assets/css/landing_public.css` / `landing_builder.css`,
  `survey/tests/test_survey_landings.py`, help page `how-to/landing-pages.md`.
- Changed: `billing/features.py`, `survey/content_screening.py`, `survey/urls.py`,
  sitemaps, the workspace sidebar, `survey/help_links.py`, locale catalogs.
- Not in this change: documents, map, results blocks, events, branding, visitor counts,
  several pages per landing, translations of a landing, API / MCP tools.
