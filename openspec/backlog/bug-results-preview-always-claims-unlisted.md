# The results-page preview always says "Unlisted", whatever the page's visibility

**Type**: bug
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-09

## Description

The live preview pane in the Public Results editor renders the public page through
`public_results_preview`, which sets `context['noindex'] = True` unconditionally
(`survey/public_results_editor.py:141`). `public_results.html` uses `noindex` to decide whether to
show a ribbon reading:

> Unlisted — viewable by direct link only, not indexed.

So a page whose **Visibility is set to Public** shows that ribbon in its own preview. Verified on the
`ameelia-mirt` page: `visibility='public'`, `is_published=True`, the editor's Visibility select reads
"Public", and the preview pane still carries the Unlisted ribbon. The live page at `/r/ameelia-mirt/`
correctly carries neither the ribbon nor a `noindex` robots tag — it serves
`<meta name="robots" content="index, follow">`.

The ribbon is describing the preview's own indexing state, not the page's. From the creator's side it
reads as a statement about their page, and it contradicts the control sitting a few centimetres to
the left.

## Notes

- Found 2026-08-09 during the pre-PR live check of `feature/public-survey-results-page`. Not a
  regression from that branch's merge with master — it is how the preview was built.
- `noindex = True` on the preview response itself is correct and should stay; a preview URL must not
  be indexed. What is wrong is reusing that same flag to drive creator-facing copy about the
  published page.
- Fix: separate the two. Keep `noindex` for the meta tag, and drive the ribbon from the page's own
  `visibility`, so the preview shows the ribbon only when the page really is unlisted. That also
  makes the preview more faithful, which is the point of a preview.
- Worth checking the same pattern elsewhere in that template — anything keyed on `noindex` or
  `preview` that produces text the creator will read as being about their page.
