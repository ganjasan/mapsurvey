## 1. Callout

- [x] 1.1 `landing.css`: `.sd-lessons`, `.sd-lesson`, `.sd-lesson__ms` (+ `.is-gap`), `.sd-lesson__tag`, mobile rules
- [x] 1.2 Template `scripts/story_tools/lessons_callout.html`; first story uses it (kept out of the repo until approved)

## 2. Card badge

- [x] 2.1 `Story.has_lessons` property
- [x] 2.2 `_story_card.html`: badge on the cover; `landing.css`: `.story-card__lessons`

## 3. Tests

- [x] 3.1 GIVEN a body with / without the callout WHEN `has_lessons` THEN True / False
- [x] 3.2 GIVEN a published story with the callout WHEN the landing renders THEN its card shows the badge, and a story without it does not
