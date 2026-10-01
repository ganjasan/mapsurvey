---
name: customer-story
description: Turn a customer's survey into a "From the field" story the way the Olney, Remington, Pszów and Whitehouse cases were done — facts from the prod DB, heat maps and phone screenshots (with the question pop-up) without touching the live survey, The goal and Lessons learned sections, story data in survey/story_data/<slug>/, a self-contained approval HTML + Remington-style cover letter, seeded to production as a draft and published from the admin after the written OK. Use for "/customer-story <slug>", "сделай историю как с Olney", "оформи кейс/story для <клиент>", "подготовь текст на согласование", "опубликуй историю на прод".
license: MIT
metadata:
  author: mapsurvey
  version: "1.1"
arguments:
  - name: slug
    description: story slug (also the survey/story_data/<slug>/ directory), e.g. remington-neighborhood-plan
    required: true
  - name: stage
    description: build (default, everything up to the approval package) | approval (rebuild only the approval HTML after edits) | publish (draft on production now, publish from the admin after the written OK)
    required: false
---

A story is the customer's work first, Mapsurvey second: their map, their words, their questions,
their marks. Every fact comes from the prod DB, every picture is either theirs (with permission)
or made by us from their survey, and nothing goes online before their written OK on the exact text
and pictures. Stories shipped this way: `olney-white-squirrel-count` (#216), then
`remington-neighborhood-plan`, `pszow-microplanning` and `whitehouse-dog-bins` (2026-10-01).
The analysis report and materials kit that usually travel with the approval letter are the
`survey-report` skill.

**Where things live**

| What | Where |
|---|---|
| Story data (source of truth, committed) | `survey/story_data/<slug>/{story.json, body.html, CREDITS.md, images/}` |
| Working notes + text drafts (gitignored) | `docs/marketing/stories/<slug>.md` |
| Customer dossier, letters, approval package (gitignored) | `docs/marketing/user-outreach/<folder>/…` |
| Permission tracker | `docs/marketing/user-outreach/PERMISSION_ASKS_2026-09-29.md` (log table at the end) |
| Approval HTML builder | `scripts/story_approval_html.py <slug> <approval.json> <out.html>` |
| Map + phone screenshot tools | `scripts/story_tools/` (see its README) |
| Installer | `python manage.py seed_story <slug> [--draft]` (idempotent by slug) |
| Guard test | `StoryDataDirectoriesTest` seeds every `story_data` dir and checks every `{img:key}` resolves |

## 0. Preconditions (stop if any is missing)

1. **Consent to be named** on record in the dossier (who, date, quoted words). Conditional consent
   ("after the survey closes") means wait, not build. Before building, re-read the
   whole thread: credit lines and roles come from the customer's own words, never paraphrased
   — some are exact and exclusive.
2. **Credit line** agreed or at least proposed in the approval asks. Some credits are exact and
   exclusive — read the lead's memory file first.
3. A **worktree** for the branch (`feature/stories-<slugs>`): `git worktree add ../Mapsurvey-<slug> -b … origin/master`,
   then the four bootstrap steps from memory `project_worktree_bootstrap` (env symlink, `.env`,
   `.env.ports` with a NEW offset registered in `.env.ports.example`, `collectstatic`).

## 1. Facts from the prod DB (read-only)

`psql "$MAPSURVEY_DB_URL" -P pager=off -X`. Columns that bite: `survey_surveysession` has
`validation_status` (not `status`), `opened_by_kind`, `is_deleted`; `survey_question` has
`survey_section_id` and `parent_question_id_id`; `survey_surveysection` has no `order_number`
(sort by `name`); `survey_answer` has `survey_session_id`. Count **clean external answered
sessions across the canonical survey + every version** (`id = X OR canonical_survey_id = X`):
not deleted, `opened_by_kind='external'`, `validation_status NOT IN ('not_approved','on_hold')`,
at least one answer. Sum answers by `q.code`, never by question id (rows are copied per version).
Device split = `survey_surveyevent.session_start.metadata->>'device_type'`; median duration =
`last_activity_at - start_datetime` over answered sessions. Write every number with its date and
query condition into `docs/marketing/stories/<slug>.md` — the approval letter and story.json quote
them, and the numbers get refreshed after the survey closes.

Export geometry for maps to the scratchpad with `\copy` (points as lat/lon, everything else as
`ST_AsGeoJSON`), and reference layers as `encode(geojson_gz,'base64')`.

## 2. Pictures without touching the live survey

Opening a customer's survey on production creates an `external` session and pollutes their data,
even as superuser. So: export the structure (`export_survey <uuid> --mode structure`, run against
prod with `SQL_*` from `$MAPSURVEY_DB_URL`, `DEBUG=0`), import it on the worktree dev stand
(`import_survey <zip> --organization <slug>`, org created first, then `status='published'`,
`admin`/`adminadmin` as owner), and screenshot there. `scripts/story_tools/README.md` has the
commands:

- **Heat maps** (`story_maps.py`): Leaflet + leaflet.heat on OpenStreetMap tiles (CARTO tiles now
  need an API key), one hue per question, `max` 5–6 so a single mark stays soft. **Marks are drawn
  as heat, never as points** — that is the sentence the customer approves. Reference layers drawn
  from the exported `geojson_gz`. Fit the bounds to the customer's boundary layer, not to the marks
  (stray marks zoom the map out). A plain map of the place with the layers makes a decent cover
  when the customer has no photo.
- **Phone screenshots** (`story_phone_shots.py`): headless Chromium 390×844 @2x; strip
  `#djDebug` before every click and shot; choose the language first when the survey has several;
  `toggleInfo(false)` collapses the panel for a map-only frame. Four frames per story:
  intro, the map, **a placed pin with its pop-up** (sub-questions answered as a demonstration —
  say so in CREDITS and the asks), one questionnaire page. To get the pop-up: click the question
  card, move the map with `setView` (find the Leaflet map object on `window`), click "Apply",
  tick a couple of choices.
- **Card image** (16:9, homepage): judge it at card size (≈400 px wide) — numbers and legend must
  survive. When the customer has a map of their decision (existing + new), redraw it ourselves at
  card size, placing their markers with `scripts/report_tools/geo.py::georeference` on features
  both maps share (e.g. the existing assets; ~1–2 m is typical), rather than cropping their image. The story's
  first big picture may be the customer's own map as is.
- Sizes: maps as JPEG q85 ≤ 1400 px wide (≈300 KB), phone frames PNG as captured (≈250 KB),
  cover JPEG 1600 wide, card JPEG 16:9 crop. Keep the directory under ~3 MB.

The Chrome extension (`mcp__claude-in-chrome__*`) is the wrong tool for this: its screenshots are
viewport-scaled and the zoom capture times out. Use Playwright from the venv.

## 3. Story data

`story.json` fields = `Story` model scalars + `cover`, `card_image`, `credit_logo` file names +
`facts` (`value`, `label`, `chip`) + `images {key: file}`. `body.html` uses the classes from
`survey/assets/css/landing.css`: `sd-figure` (`--tall`, `--photo`, `--poster`), `sd-phones` >
`sd-phone` > `sd-phone__frame`, `sd-quote`, `sd-legend`; pictures as `{img:key}`. Sections that
worked: the place · **The goal** (why the survey was made: the decision the customer faced, the
budget or plan behind it, what they wanted from residents — facts from their own documents, in
our words, no attribution unless they wrote it) · in their own words (a verbatim quote of their
intro or closing page) · the survey (questions + phone frames) · what came back (numbers + heat
maps) · what they did with it (their decision, if any) · **Lessons learned** · what's next.

**Lessons learned** is one callout with the same look in every story (`<aside class="sd-lessons">`,
styles in `landing.css`; copy the template `scripts/story_tools/lessons_callout.html`, it carries
its own SVG marks). Lessons
come from the customer's words in the thread and from prod data (versions republished after
launch, opens vs answers, reshare waves); 3–5 of them, each a short imperative headline + one
sentence of evidence. Under each, an "In Mapsurvey" line: what the product has for it, tagged
`Available`, `Built for <customer>` or `Not yet` (`is-gap`, dashed mark) — check every claim in
the code before writing it, and never present a gap as a feature. A story with the callout gets
the "Lessons learned" badge on its card automatically (`Story.has_lessons`). Don't repeat a lesson
in "What's next". Never claim outcomes the
project has not produced; never publish aggregates the customer has not released. `CREDITS.md`
lists every file's source and permission state.

Seed locally (`seed_story <slug>` with the dev stand's env), open `/stories/<slug>/` and the
landing, screenshot full page, look at it. Run
`./run_tests.sh survey.tests.StoryDataDirectoriesTest survey.tests.SeedStoryTest`.

## 4. Approval package

`docs/marketing/user-outreach/<folder>/<slug>-approval.json` (reviewer, headline, intro, numbered
asks, optional `legend`/`card_note`/`new`) → `python scripts/story_approval_html.py <slug>
<json> docs/marketing/user-outreach/<folder>/<slug>-story-for-approval.html`. The page shows the
homepage card, the story page and the asks; images are embedded so it opens from an email
attachment. On a second round, mark changed text with `<div class="new">` / `<span
class="tag">new</span>` in body.html and set `legend` — remove the markers before the final seed.

Cover letter `correspondence/<date>_story-and-report-draft.md` in the **Remington format** (the
letter the owner approved on 2026-10-01): "Hi <name>," · thanks · one sentence that the story is
attached as it would look (card + page), "Nothing goes online before your answer, and anything you
say no to comes out. A short yes or no on each point is plenty:" · 4–6 numbered asks (credit line
+ logo; their quote; screenshots + heat maps, the pop-up pin is a demonstration; the numbers; any
sentence they must confirm) · "Separately: I am building a reporting module for Mapsurvey…" with
the kit from `survey-report` · "I would love to know what is useful in it and what is missing." ·
"Best, Artem". Keep the approval HTML's asks identical in number and order to the letter's.
Also produce single-page PDFs of the approval page and the report (`scripts/report_tools/pdf.py
--single`) — customers forward PDFs. Show To + Subject first; the owner sends by hand; record
`SENT` in the draft, the reply as `<date>_story-approval-received.md`, the tracker row, the lead's
memory and the Stack item (waiting on the customer).

## 5. Production: draft now, publish on the OK (change `story-draft-publishing`)

1. Get the story onto production **without the repo** while it waits for the OK: keep
   `survey/story_data/<slug>/` untracked (`.git/info/exclude`), stream it to the web instance and
   seed from there:
   `tar czf - -C survey/story_data <slug> | ssh <web-service-id>@ssh.oregon.render.com 'mkdir -p /tmp/stories && tar xzf - -C /tmp/stories'`
   then on the instance (`cd /home/app/web`) `python manage.py seed_story <slug> --from /tmp/stories/<slug>`.
   (The service id is in the owner's notes, not in this public repo.) Commit the directory to
   the repo only after the OK. The command: a new story is installed as a **draft**, a re-run keeps
   its state. Open `https://mapsurvey.org/stories/<slug>/` signed in as staff: the page shows a
   "Draft — not public" banner and is `noindex`; visitors get 404 and it is off the landing,
   `/stories/` and the sitemap.
2. On the written OK: apply their edits to `body.html` / `story.json`, strip review markers,
   re-seed, then **Admin → Stories → Publish** (or the list checkbox). Don't `--publish` from the
   command line for a story that waited for an OK; the admin step is the record that someone
   checked.
3. Verify the page and the landing carousel, update the dossier, the tracker, memory and Stack;
   schedule the numbers refresh (survey close date).

## Rules that are easy to break

- **A conditional or missing OK is a stop for publishing, not for preparing**: build, send for
  approval, seed as a draft — publish only after the written OK.
- **The repo is public.** Everything under `survey/story_data/` is readable on GitHub the moment
  it is pushed, draft or not. Unapproved text and pictures do not go to `master`.
- **Do not open the customer's live survey** to take screenshots or "check something". Export,
  import, look locally.
