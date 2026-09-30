## 1. Model

- [x] 1.1 `Story`: add `place`, `sector`, `summary`, `credit`, `credit_note`, `credit_logo`,
  `card_image`, `cover_alt`, `cover_credit`, `facts`; add `case-study` to `STORY_TYPE_CHOICES`
- [x] 1.2 `StoryImage` (story FK, `key`, `image`, unique per story+key), `upload_to='stories/'`
- [x] 1.3 Migration `0087_story_showcase`
- [x] 1.4 `StoryAdmin`: fieldsets for the new fields, `StoryImage` inline

## 2. Rendering

- [x] 2.1 `survey/stories.py`: `render_body(story)` resolves `{img:key}` tokens; `story_detail`
  passes `body_html`
- [x] 2.2 `story_detail.html` rebuilt after the mockup (eyebrow, title, lead, byline, cover with
  caption, facts, body, CTA); keep canonical/breadcrumb/meta blocks
- [x] 2.3 `partials/_story_card.html` rewritten (card image, type, where, title, summary, chips,
  credit); `stories_index.html` keeps using it
- [x] 2.4 `landing.html`: "From the field" carousel between hero and showcase, hidden without
  published stories; inline scroll-snap JS
- [x] 2.5 `landing.css`: carousel, card, story-detail figures/quote/facts/phones/CTA; remove the
  old `.story-card` rules they replace; `collectstatic`

## 3. Seed command and the Olney story

- [x] 3.1 `seed_story <slug> [--draft]` reading `survey/story_data/<slug>/`
- [x] 3.2 `survey/story_data/olney-white-squirrel-count/`: `story.json`, `body.html`, `images/`
  (cover, card, logo, sign, route map, poster, resident photo, heat map, four phone screenshots)
  with the 2026-09-30 wording; a `CREDITS.md` naming each image's source
- [x] 3.3 Run the command locally, open `/` and `/stories/olney-white-squirrel-count/`, compare
  against the mockups

## 4. Tests (GIVEN / WHEN / THEN)

- [x] 4.1 Detail page renders eyebrow, lead, credit, facts, and resolves an image token to the
  stored file's URL; an unknown token renders an empty `src`, not a 500
- [x] 4.2 Landing shows the carousel with a published story's card and omits the section when
  none is published; the unpublished story never appears
- [x] 4.3 `seed_story` on an empty database creates the published story with its images; a
  second run updates the text and keeps the slug, id and `published_date`; `--draft` leaves
  `is_published` False; unknown slug → `CommandError`
- [x] 4.4 Sitemap lists the seeded story (existing test extended if needed)

## 5. Docs

- [x] 5.1 `CLAUDE.md`: one paragraph on stories — repo is the source, `seed_story`, tokens
- [x] 5.2 Spec deltas in `specs/public-stories/spec.md`
