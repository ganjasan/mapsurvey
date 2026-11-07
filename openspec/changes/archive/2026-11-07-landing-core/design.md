## Context

Epic #348 (Vision and Scope: ops `requirements/vision/landing-pages.md`). The owner decided on
2026-11-07: a Landing is its own workspace entity; surveys link to it many-to-many; one long
page; a simple block builder with a closed set of types; the whole feature is Pro. The closest
existing pieces are the public results page (`PublicResultsPage` + ordered `PublicResultsBlock`,
`/r/<slug>/`), the map style library (a workspace-owned Pro object with its own pages and a
sidebar row), the creator rich-text path (`coerce_creator_html`), `layer_assets.embed_url`
(YouTube / Vimeo), `share.qr_image`, `schedule.phase`, and content screening.

## Goals / Non-Goals

**Goals**: a Pro workspace builds a landing in minutes, links its surveys, publishes it at a
stable `/p/<slug>/` that reads well on a phone, and the link keeps working through a lapse.
One validator per block type, so what the builder saves is what the page can draw.

**Non-Goals**: styling, columns, several pages, translations of a landing, documents, map,
results, events (later steps), visitor counts, API / MCP tools, a landing list on the dashboard.

## Decisions

### D1. Three models, blocks keep their data in one JSON field
`Landing(uuid, organization FK CASCADE, title ≤120, summary ≤300 plain text, cover ImageField
on the public tier under a random key, slug unique ≤64, language, visibility public|unlisted,
is_published, published_at, created_by, created_at, updated_at)`.
`LandingSurvey(landing FK CASCADE, survey FK CASCADE → canonical SurveyHeader, order)`, unique
`(landing, survey)`. `LandingBlock(landing FK CASCADE, order, kind, title ≤120, data JSON,
image ImageField public tier random key, landing_survey FK CASCADE null)`.

Per-kind fields live in `data` and pass ONE function, `landings.clean_block(kind, raw) ->
(data, errors)`, on every write. A new block type (#577–#579) is one entry in
`landings.BLOCK_KINDS` plus its cleaner and its template — never a column. A survey card points
at its `LandingSurvey` row, so unlinking a survey removes its cards with it (CASCADE) and a card
can never show a survey the landing does not link.

Several pages later: a `LandingPage` table and a nullable FK on `LandingBlock`, existing blocks
moved to page 1 in the migration. Nothing in this change prevents that.

### D2. The block set and its data
| kind | `data` | notes |
|---|---|---|
| `text` | `{body}` | rich text, `coerce_creator_html`, ≤ 20 000 chars |
| `image` | `{alt, caption}` + `image` file | alt ≤200, caption ≤300; jpg/png/webp/gif ≤ 5 MB |
| `button` | `{label, url, style}` | label ≤60; url absolute http(s) only; style `primary|secondary` |
| `video` | `{url, embed, caption}` | `layer_assets.embed_url(url)` decides; stored `embed` is the player URL |
| `faq` | `{items: [{q, a}]}` | 1–30 items; `q` plain ≤200, `a` rich text ≤ 4 000 |
| `timeline` | `{items: [{title, when, body}], current}` | 1–12 phases; `when` free text ≤60 ("March 2027"); `current` index or null |
| `survey` | `{button_label}` + `landing_survey` | label optional ≤40 |

`title` on any block is an optional heading; a block with a title becomes an entry in the
page's anchor navigation (`#b-<id>`). Phases carry free-text dates because creators write
"Spring 2027" and "after the council vote", not instants; `current` marks the phase the
engagement is in, everything before it is drawn as done.

### D3. Survey cards read the survey's state at render time
`landings.survey_card(landing_survey)` → `{state, url, results_url, opens_at, closes_at}`:
published + `schedule.phase` open → `open` with the survey's public URL
(`embedding.survey_url_on(share.base(), survey)`); `before` → `upcoming` with the opening
date; `after` or `closed` → `closed`, with the `/r/` link when a published results page exists;
`draft`/`testing` → `upcoming` without a date ("Coming soon"); `archived`, trashed or held by
screening → the card is not drawn on the public page (the builder shows why). Nothing is copied
onto the landing, so a survey closing or opening needs no landing edit.

### D4. Pages, URLs, roles
Builder pages live under `/editor/landings/` (the sidebar shows there) and extend `base.html`
like the map style library, loading HTMX, SortableJS and Quill in `extra_head`: list `editor_landings`, create `editor_landing_create` (POST),
builder `editor_landing` (`/editor/landings/<uuid>/`), and POST endpoints for settings, link /
unlink / reorder surveys, add / edit / delete / reorder blocks, publish / unpublish, delete.
A landing is looked up by uuid and authorised against ITS organisation (`get_org_membership`),
never the active one: owner / admin / editor act, viewers see the builder read-only, outsiders
get 404. Block add/edit answer the re-rendered block list (HTMX swap); reorder takes a JSON body
`{"order": [...]}` and renumbers 0..N like `public_results_blocks_reorder`. The sidebar gets a
MODULES row *Landing pages* (`fas fa-flag`) with the `landing_pages` Pro mark; active for url
names starting `editor_landing`.

Survey picker: the workspace's canonical surveys that are not trashed or archived.

### D5. Public page
`/p/<slug>/` (`views.landing_public`) on a new base, `landings/public.html`, that extends
nothing creator-side: own minimal CSS (`css/landing_public.css` — `landing.css` is the marketing site's), no Bootstrap, no PostHog (prefix `/p/` added to `POSTHOG_EXCLUDED_PREFIXES` — visitors are our
customers' residents, the same rule as `/surveys/` and `/r/`), `<html lang>` from the landing's
language. Order: hero (title, summary, cover), anchor nav (titled blocks), blocks, footer
(organisation name, "Made with Mapsurvey" unless `unbranded`, report link).
Not published, or held → `survey_unavailable.html` 404 for everyone except members of the
owning workspace, who see the page with a "Draft — only your workspace sees this" banner
(that is the builder's Preview). Unlisted → `<meta name="robots" content="noindex">` and no
sitemap entry. Public + published → sitemap entry. OG tags: title, summary, cover.

### D6. Pro gate and the lapse rule
`billing.features`: `landing_pages` (Pro), trial allowance 1 (landings created). Create, every
builder POST and publish check `trial.may(org, 'landing_pages')` and refuse with
`billing/feature_required.html` (403); create calls `trial.use`. The builder GET opens for a
lapsed workspace in read-only mode with the upgrade banner, so the creator can still see and
unpublish. The public page never checks the plan: a landing published while Pro stays online
after a lapse — a printed QR code must not die with a card payment. Unpublish is always allowed.

### D7. Screening covers landings — one review table
`ContentReview.survey` becomes nullable, `ContentReview.landing` (FK, nullable) is added, with a
CheckConstraint "exactly one of survey, landing". `content_screening`:
`collect_landing_text(landing)` (title, summary, every block's title and texts, FAQ, phases,
button labels and URLs as the redirect-like link list), `screen_landing(landing, trigger)`
sharing `_hold(anchor, inp, trigger)` with `_screen`, `is_landing_held(landing)`.
Triggers: publish, and any builder save while published. Report: `/p/<slug>/report/` with the
same form and rate limit, `report_landing()`. Notice mail and the staff review page take a
`subject` (kind, name, public URL, editor URL) instead of reading `review.survey` directly;
`confirm_phishing` on a landing review deactivates the creator, closes their surveys (as today)
and unpublishes their landings.

### D8. Slugs
Created from the title (`slugify`, ≤ 64, numeric suffix on collision), editable in settings;
`[a-z0-9-]`, 3–64 chars, reserved words (`new`, `edit`, `report`, `admin`) refused. Changing the
slug of a published landing warns that printed links break; the old slug is not kept.

## Risks / Trade-offs

- [JSON block data drifts from what templates expect] → every write passes `clean_block`;
  templates read only cleaned keys; a test round-trips every kind.
- [Survey card leaks a draft survey's name] → a draft card says "Coming soon" with the name the
  creator chose to show; linking is the creator's explicit act. Held / archived surveys draw nothing.
- [Two mechanisms for "this page is down"] → the landing uses the survey's `survey_unavailable`
  404 and the same review table, not a flag of its own.
- [Making `ContentReview.survey` nullable] → every existing reader goes through the review's
  subject; `RunPython` not needed (no data changes); the index stays.

## Migration Plan

One additive migration in `survey` (three tables, ContentReview FK + constraint). Rollback =
revert; no data outside the new tables. Pre-deploy migration is safe for the old instance: the
only change to an existing table makes a column nullable and adds one.
