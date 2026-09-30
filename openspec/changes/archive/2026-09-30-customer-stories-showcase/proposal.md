## Why

The first paying municipal customer, the City of Olney (Illinois), gave written permission on
2026-09-29 to be shown on the homepage and to have its White Squirrel Count told as a story, and
returned its edits on 2026-09-30. The site has a `Story` model, `/stories/` and `/stories/<slug>/`,
but production holds zero stories, the landing page dropped its stories section in an earlier
redesign, and the model cannot hold what the approved mockups
(`docs/marketing/homepage/olney-story.mockup.html`, `homepage-social-proof.mockup.html`) show:
place and sector, a lead, a credit line with a logo, fact chips, a captioned cover, and images
inside the body. There is also no way to get a story onto a Render PR preview or onto production
other than typing it into the admin and uploading files by hand — the story content has to live in
the repo, like the Copenhagen demo does, so a preview can show it and production can be updated by
one command.

## What Changes

- **Story model grows the fields the story page needs**: `place`, `sector`, `summary`, `credit`,
  `credit_note`, `credit_logo`, `card_image`, `cover_alt`, `cover_credit`, `facts` (list of
  value/label pairs); a `case-study` story type. New `StoryImage` rows (story FK, `key`, image)
  hold the pictures a body refers to as `{img:key}` tokens, resolved to storage URLs at render
  time — the body stays portable between environments whose media prefixes differ.
- **Story detail page rebuilt** after the mockup: eyebrow (place · sector), title, lead, byline
  with the credit logo, captioned cover, fact strip, body, and a shared "build your own" CTA.
  Body figures, quotes and the phone-screenshot grid get CSS in `landing.css`.
- **Homepage "From the field" carousel** of published stories between the hero and the product
  showcase; one card partial serves the carousel and `/stories/`. Hidden when nothing is
  published.
- **`seed_story <slug>` management command** installs or refreshes one story from
  `survey/story_data/<slug>/` (`story.json` + `body.html` + `images/`), uploading the images to
  the public media tier. Idempotent by slug. `--draft` seeds it unpublished.
- **The Olney story** committed under `survey/story_data/olney-white-squirrel-count/` with the
  2026-09-30 wording and the images named in the approval letter. Publication on production
  waits for Kelsie Sterchi's written OK on the ten asks; this change only makes it possible.

## Capabilities

### Modified Capabilities
- `public-stories`: richer Story model, StoryImage, the rebuilt detail page, the homepage
  carousel restored, the seed command.

### New Capabilities
<!-- none -->

## Impact

- **Models / migration**: `survey/models.py` (`Story` fields, `StoryImage`), `0087_story_showcase`.
- **Admin**: `StoryAdmin` gains the new fields and a `StoryImage` inline.
- **Views**: `story_detail` resolves image tokens; `index` already passes `stories`.
- **Templates**: `landing.html` (carousel), `partials/_story_card.html` (rewritten),
  `story_detail.html` (rebuilt), `stories_index.html` (uses the new card).
- **CSS**: `survey/assets/css/landing.css` — carousel, card, story-detail figure/quote/facts/CTA.
- **Command + data**: `survey/management/commands/seed_story.py`,
  `survey/story_data/olney-white-squirrel-count/` (~3.3 MB of images).
- **Tests**: model/detail/carousel/seed tests in `survey/tests.py`.
- **No** new dependencies, no change to respondent surfaces.
