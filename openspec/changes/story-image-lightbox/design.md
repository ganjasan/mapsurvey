## Context

`story_detail.html` renders staff-authored HTML with `<figure class="sd-figure">` blocks and a
`.sd-phones` grid of `<figure class="sd-phone">`; the cover is a `.sd-figure--hero`. The landing
page has `#shotLightbox` (image only, no caption, no navigation) with its own inline script.

## Decisions

### D1. One script, DOM-driven, no data attributes in the body
`story_lightbox.js` collects every `<img>` inside `.story-detail` except the credit logo
(`.sd-org img`) at load time, in document order. The caption comes from the nearest
`figure > figcaption` text, falling back to `alt`. Authors write plain figures; nothing in
`body.html` has to know about the lightbox — the Olney body needs no change.

### D2. Separate markup and classes from the showcase lightbox
`.story-lightbox` reuses the showcase backdrop look (same colours, blur, close button) but is
its own block: it needs a figure with caption, two nav buttons and a counter, and the showcase
one must not grow those. Shared values are copied, not abstracted — two small blocks beat a
premature base class.

### D3. Keyboard and focus
Open: remember the clicked picture, focus the close button. `Escape` closes, `ArrowLeft` /
`ArrowRight` step (wrapping). Close: restore focus to the picture. Body scroll is locked while
open, as the showcase does. The dialog is `role="dialog" aria-modal="true"` with the caption as
`aria-describedby`.

### D4. Full-resolution source
The `src` in the page is already the stored file (≤1440 px); the lightbox shows the same URL at
`max-width: 96vw; max-height: 86vh` with `object-fit: contain`. No second size is generated.

## Risks / Trade-offs

- A picture inside a link would open the lightbox and follow the link: the script calls
  `preventDefault` only for images not inside an `<a>`, so linked pictures keep their link.
- Touch: swipe is not implemented; the nav buttons are 44 px and reachable with a thumb.
