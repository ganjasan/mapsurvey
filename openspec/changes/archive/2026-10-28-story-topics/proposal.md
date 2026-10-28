## Why

Stories are the strongest content on mapsurvey.org and they are islands: a story links to nothing but the sign-up CTA, and no landing page links to a story. Competitors rank for "community engagement platform" and "participatory budgeting" largely because every case study sits inside the topic cluster of the page that sells it (issue #250, epic #257). Topics turn each story into an internal link to its landing page and each landing page into a showcase of the stories that prove it.

## What Changes

- A topic registry, `survey/topics.py`: slug, label and, where the page exists, the key of the SEO landing it belongs to. Topics without a landing are allowed and mark demand for one.
- `Story.topics`: a list of topic slugs, set in `story.json`, installed by `seed_story` (unknown slugs are an error), editable in the admin.
- The story page shows its topics as chips under the eyebrow; a chip links to the landing page when the topic has one.
- `/stories/` gets a topic filter row (`?topic=<slug>`); the canonical stays `/stories/`.
- Every SEO landing page shows a "From the field" block with the published stories that carry its topic, using the shared story card, placed before the FAQ. Omitted when there are none.
- The existing repo story (`olney-white-squirrel-count`) is tagged; the three stories seeded from the ops repo are tagged through their ops `story.json` and the admin.

## Capabilities

### New Capabilities
- `story-topics`: the topic registry, the story field, the chips, the index filter and the landing block.

### Modified Capabilities
- `public-stories`: the Story model gains `topics`; the detail page shows them.

## Impact

- `survey/models.py` (+ migration `0092`), `survey/topics.py` (new), `survey/management/commands/seed_story.py`, `survey/admin.py`.
- `survey/seo_landings.py::render_seo_landing` (topic stories in context), `survey/views.py` (`stories_index` filter).
- Templates: `story_detail.html`, `stories_index.html`, new `partials/_topic_stories.html`, one include line in each of the 12 SEO landing templates; `css/landing.css`.
- `survey/story_data/olney-white-squirrel-count/story.json`, `survey/tests.py`.
