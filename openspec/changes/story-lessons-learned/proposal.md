## Why

Customer stories carry what the customer found out while running the survey (a question renamed
minutes after launch because residents could not find the button). Readers planning their own survey look
for exactly that. It needs one recognisable look in every story, like the margin icons in
technical books, and a marker on the card so a reader can spot stories that have it.

## What Changes

- A "Lessons learned" callout for story bodies: `<aside class="sd-lessons">` with a fixed mark
  (a benchmark pin in a stamped ring), numbered lessons, and under each lesson an "In Mapsurvey"
  line with a status tag (Available / Built for … / Not yet, the last with a dashed mark).
  Styles in `landing.css`; the marks are inline SVG symbols inside the aside, so `body.html`
  stays self-contained.
- `Story.has_lessons` (no migration): true when the body contains the callout.
- The story card shows a "Lessons learned" badge on its cover when `has_lessons`.
- Template: `scripts/story_tools/lessons_callout.html`. First use: a story still awaiting its
  customer's approval, so not in the repo yet.

## Impact

- `survey/models.py` (property), `partials/_story_card.html`, `landing.css`, tests.
- No model field, no migration. A filter by lessons on `/stories/` is out of scope until two or
  three stories carry the callout.
