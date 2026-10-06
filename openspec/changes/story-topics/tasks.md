## 1. Registry and model
- [x] 1.1 `survey/topics.py`: `Topic`, `TOPICS`, `by_slug`, `for_landing(key)`, `validate_slugs`
- [x] 1.2 `Story.topics` JSONField + migration `0092_story_topics`
- [x] 1.3 `seed_story`: `topics` in `SCALAR_FIELDS`, validated before the transaction
- [x] 1.4 Admin: `topics` on the form with registry validation

## 2. Story page and index
- [x] 2.1 `story_detail.html`: chip row under the eyebrow, link when the topic has a landing
- [x] 2.2 `stories_index`: `?topic=` filter, used-topics chip row, canonical unchanged
- [x] 2.3 CSS for the chip row and the filter row

## 3. Landing block
- [x] 3.1 `render_seo_landing`: `topic` + `topic_stories` in context
- [x] 3.2 `partials/_topic_stories.html` with the shared card
- [x] 3.3 Include it before the FAQ in all 12 landing templates

## 4. Data
- [x] 4.1 Tag `olney-white-squirrel-count/story.json`
- [x] 4.2 The three production stories have no story.json in the ops repo; they are tagged in the admin after deploy (see PR)

## 5. Tests and docs
- [x] 5.1 Tests for every scenario in both delta specs (GIVEN / WHEN / THEN)
- [x] 5.2 Run story, landing and SEO test classes, then the full suite once
- [x] 5.3 Browser check on the dev server: story page, filtered index, a landing with and without stories
- [x] 5.4 CLAUDE.md paragraph on topics
