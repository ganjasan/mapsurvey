## 1. Lightbox

- [x] 1.1 `survey/assets/js/story_lightbox.js`: collect story pictures, open with caption and
  counter, prev/next with wrap, close on cross / Escape / backdrop, arrow keys, focus handling
- [x] 1.2 `story_detail.html`: lightbox container (`#storyLightbox`, dialog semantics, translated
  labels) and the script include
- [x] 1.3 `landing.css`: `.story-lightbox` block (backdrop, figure, caption, nav, counter, close)
  and `cursor: zoom-in` on story pictures; `collectstatic`

## 2. Verification

- [x] 2.1 Test: the story page contains the lightbox container and the script; a story without
  pictures still renders 200 with the container (script is a no-op)
- [x] 2.2 Open the Olney story locally, click the route map and a phone screenshot, step with
  buttons and arrows, close with cross, Escape and backdrop; check at 390 px
- [x] 2.3 Spec delta in `specs/public-stories/spec.md`
