## Why

The Olney story (change `customer-stories-showcase`) shows a route map with 46 labelled zones,
four 390-px phone screenshots and a heat map — all sized to the 720-px reading column, where
the zone labels and the phone UI are too small to read. The owner asked for a lightbox: click a
picture, see it large with its caption, close with the cross or Escape, step to the previous
and next picture of the same story. The landing page already has a bare lightbox for the
product screenshots (`#shotLightbox`); stories need captions and navigation on top.

## What Changes

- Every picture in a story page (cover and body figures, including the phone frames) opens in
  a **lightbox**: the image at up to viewport size, its caption (the figure's `figcaption`, else
  the alt text), a counter, previous/next buttons, a close button.
- Closes on the cross, Escape, or a click on the backdrop; `←`/`→` step; steps wrap within the
  story. Focus goes to the close button on open and returns to the picture on close.
- Pictures get a `zoom-in` cursor; nothing changes for a story without pictures. No library:
  `survey/assets/js/story_lightbox.js` + CSS in `landing.css` beside the showcase lightbox.

## Capabilities

### Modified Capabilities
- `public-stories`: story detail page pictures open in a lightbox with caption and navigation.

## Impact

- `survey/templates/story_detail.html` (lightbox container + script include),
  `survey/assets/js/story_lightbox.js` (new), `survey/assets/css/landing.css`,
  `survey/tests.py` (markup present, script served). No model or view changes.
