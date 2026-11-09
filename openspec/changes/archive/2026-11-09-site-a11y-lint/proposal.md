## Why

Issue #609 (epic #348, Sites v1.1 wave A, story S13, first half). Councils publishing a site are bound by accessibility law (the European Accessibility Act, national public-sector rules); the creators are planners, not web specialists, and need the builder to point at what a screen-reader or keyboard user would trip over.

## What Changes

- Builder checks (`sites.a11y_issues`): a picture or the cover without a description; a small heading before any large or medium one; a link or a button that says only "here" / "more" / "click here". Each issue is a note under the block on the canvas and an icon on its outline row; the Publish popover lists them with links to the blocks. Publishing is never blocked.
- Public page: a "Skip to content" link, a visible focus ring on every control, `<main id="main">`.
- Contrast and the conformance note on `/trust/` stay in wave C (they depend on branding colours).

## Capabilities

### Modified Capabilities
- `survey-sites`: accessibility checks in the builder; keyboard basics on the public page.

## Impact

`sites.py`, `site_views.py`, templates `_canvas_block.html`, `_outline_item.html`, `builder.html`, `public.html`, CSS, help, catalogs. No migration.
