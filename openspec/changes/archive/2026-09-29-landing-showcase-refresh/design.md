## Context

Screenshots come from the local seed of the Copenhagen demo (`seed_demo_survey`), identical to production. The page is rendered at a 1440×900 layout and captured at 1920×1200 (CSS `zoom: 1.3333` on a 1920×1200 viewport: the layout is the 1440 one, the pixels are full resolution), then saved as WebP at 1920×1200 for the lightbox and 1200×750 inline, the sizes the existing markup expects.

## Decisions

- **Build shows the layer editor, not the AI draft screen**: the layer editor carries the newest and most distinctive part of building (your own data with photos and categories), and the AI draft is already in the step's copy. The survey editor's section form was tried and rejected: it is a form of text fields and, for a published survey, shows the subheading's raw HTML.
- **Share shows the top of the results page**, not a map block: under CSS zoom Leaflet's default marker shadows drift off their pins; the page top (title, sample-answer disclosure, response count, "Take the survey", first chart) reads as a published page at thumbnail size.
- **Six capability cards, same grid**: the 3×2 grid and card markup stay; only icons and copy change, so no CSS work and no layout risk on phones.
- **`hasSize` reads the container** (`clientWidth/clientHeight`), never `map.getSize()`; `whenSized` already calls `invalidateSize()` before `ready`, so Leaflet's own size is fresh when features are drawn.
- **Overview start view is a map option** (`center`, `zoom`), so nothing can run after `ready` and undo the fit.

## Risks / Trade-offs

- [Screenshots age again] → they come from a seeded, reproducible survey; retaking them is a documented procedure (this design), not a hunt for a good-looking account.
- [The `hasSize` change touches every Responses map] → it only makes `ready` run in cases where it silently did not; the Map pane, drawer and session modal were checked in the browser.
