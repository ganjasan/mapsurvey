## Context

`Story` (title, slug, body, cover_image, story_type, survey, is_published, published_date) was
built for a card grid that has since been redesigned away. The approved Olney mockups need a
place/sector eyebrow, a lead paragraph, a credit line with the City's logo, four fact chips, a
captioned cover, seven images inside the body (route map, poster, sign, resident's photo, heat
map, four phone screenshots) and a closing CTA. Production has no stories; PR previews start
from an empty database and no shell (jobs only). `docs/` is gitignored, so nothing under
`docs/marketing/` can be the source of truth for what the site shows.

## Goals / Non-Goals

**Goals**
- One story row carries everything the detail page and the card show; no per-story template.
- Story content (text + images) is committed and installed by a command, the way
  `seed_demo_survey` installs the Copenhagen demo — previews and production get the same bytes.
- The homepage shows published stories again, in the carousel the mockup shows.
- Nothing reaches production's homepage until the command is run there by hand.

**Non-Goals**
- A CMS. Stories are written by us, in HTML, in the repo; the admin is for toggles and typos.
- Live maps inside stories (the heat map is a static image on purpose — live points would
  expose residents' backyards).
- Pszów and Remington stories — placeholders in the mockup, not part of this change.
- Translations of stories.

## Decisions

### D1. Body images are `StoryImage` rows referenced by `{img:key}` tokens
The body is HTML with `<img src="{img:route-zones}">`. `story_detail` replaces every
`{img:<key>}` with the URL of the `StoryImage` of that key (missing key → empty `src`, never a
500). Alt text and captions stay in the HTML, where the author controls the figure markup
(`sd-figure--tall`, `--poster`, the phone grid).

*Why not absolute media URLs in the body:* media prefixes differ per environment
(`previews/mapsurvey-pr-N/media` vs `media`), and S3 vs local storage; a body written for one
would break on the other.
*Why not a Markdown renderer:* the figures need classes and a legend the mockup defines; a
renderer adds a dependency for one page type.

### D2. The card image is its own field, falling back to the cover
Olney's card uses the resident's squirrel (wide crop); the detail page opens on the volunteers'
photo. `card_image` optional, `cover_image` required for the card to have a picture at all.

### D3. Facts are a JSON list, not four columns
`facts = [{"value": "1977", "label": "first count"}, …]`, rendered as chips on the card and as
the fact strip on the page. Zero to six entries; the template renders what is there.

### D4. `seed_story <slug>` reads `survey/story_data/<slug>/`
- `story.json`: every scalar field plus `images: {key: filename}` and `cover`, `card_image`,
  `credit_logo` filenames.
- `body.html`: the body with tokens.
- `images/`: the files.
Upsert by slug; images are re-uploaded under `stories/<slug>/<filename>` each run (the public
storage has `file_overwrite = False`, so a re-run gets a suffixed name and the row is pointed at
it — old objects are left behind, acceptable for a handful of files). `is_published` is set
True unless `--draft`; `published_date` is taken from `story.json` and only set if empty, so a
re-run keeps the original date.

*Why a command, not a data migration:* the story will be refreshed after the October count and
whenever Kelsie asks for a change; migrations are one-shot and would carry 3 MB each.

### D5. Placement on the homepage
The carousel sits between the hero and the product showcase, as in the mockup — the first
thing under the fold is who uses the product. The section is omitted when no story is
published (spec requirement kept). The carousel JS from the mockup (two buttons, scroll-snap)
goes inline in the template; no library.

### D6. Story type
Add `case-study` ("Case study") to `STORY_TYPE_CHOICES`; the four existing labels stay.

## Risks / Trade-offs

- **3.3 MB of images in git.** Accepted: the Copenhagen demo already carries photos; stories are
  few. Photos are pre-sized to what the page displays (≤1440 px).
- **Body is rendered `|safe`.** Unchanged from today; only staff write it. Not creator input, so
  `coerce_creator_html` does not apply.
- **Re-running the seed after an admin edit overwrites the edit.** By design — the repo is the
  source; the admin is for `is_published`.
- **Permission**: the poster family photo (children) and the resident's photo are in the data
  directory before Kelsie's final yes. The data directory is not the site; `seed_story` on
  production is a manual step and is not run until she answers. If she says no to an image,
  it is removed from the repo before that.

## Migration Plan

1. `0087`: add nullable/blank fields to `Story`, create `StoryImage`. Additive; no backfill.
2. Deploy; nothing visible changes (production has no stories).
3. On a PR preview: run `seed_story olney-white-squirrel-count` as a Render job to review.
4. After Kelsie's OK: run the same command on production over Render SSH.

## Open Questions

- Whether `/stories/` should link the live results page `/r/olney-white-squirrel-count/` —
  ask #9 in the approval letter; the data file carries no link until she answers.
