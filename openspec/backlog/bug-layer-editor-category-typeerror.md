# Layer object editor throws `TypeError: ... reading 'category'` while a creator edits objects

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-09-21
**Status**: root cause found and fixed — change `fix-layer-editor-stale-visible-list`

## Description

PostHog error tracking captured three uncaught `TypeError: Cannot read properties of
undefined (reading 'category')` from `js/layer_editor.js` on 2026-09-18, all in one
session (person `469`, Edge 153 / Windows) on
`/editor/surveys/f1c14d7b-26e1-46a7-b6c9-7ad0e3339607/layers/195/edit/`, over 2.5
minutes — 13:12:31, 13:12:33, 13:15:00. A creator repeating an action that kept failing.

[PostHog issue](https://eu.posthog.com/project/248938/error_tracking/01a0b4a5-b0c1-72c2-9bed-a199c93f3a5b)

## Root cause (established 2026-09-21, reproduced in a browser)

Not in `fillCard()` or `featureFromDetail()`, the two sites the first pass suspected.

The list keeps its filtered order in `visible` (an array of keys) and its data in `byKey`
(a key→row map). `renderRows()` does `var o = byKey[visible[i]]` and touches `o.category`
with no check — `category` is simply the **first property read off the missing row**, which
is why the message names it. Nothing enforced that the two structures agree, and
`renderRows()` is reachable from four places that are not `recomputeVisible()`: the list's
`scroll` listener, the window's `resize` listener, `select()` and `closeCard()`.

Two windows where they disagreed:

1. `reloadAll()` (after every CSV / GeoJSON / photo import) replaced `objects`/`byKey`
   synchronously but only recomputed `visible` after the layer-GeoJSON `fetch` returned —
   megabytes on a large layer. A scroll or resize in that window throws from a plain event
   listener: **uncaught**, `handled: false`, exactly what PostHog recorded.
2. `removeLocal()` deleted from `objects`/`byKey` and then, for the selected object, called
   `closeCard()` → `renderRows()` before its callers reached `recomputeVisible()`. That one
   sits inside a promise `.then`, so the surrounding `.catch` turned a **successful
   deletion** into `status('error', 'Cannot read properties of undefined (reading
   category)')` with the row still on screen.

Both reproduced on `HEAD`'s file in a seeded editor: the delete path showed that exact
error text in the status bar with the count unchanged, and scrolling afterwards raised the
uncaught `TypeError`.

A third defect of the same class was found while auditing: `reloadAll()` left `current`
pointing at a key the import had replaced, and the Delete button reads
`byKey[current].title`.

## Fix

In change `openspec/changes/fix-layer-editor-stale-visible-list/` — restore the invariant
where the state changes (`reloadAll`, `removeLocal`), close the card when the selected
object is gone, and make `renderRows()` skip a missing row so no future desync can produce
an uncaught exception. Verified in a browser; see that change's `tasks.md` for the
before/after runs.

## Notes

- The single-source-of-truth refactor (one array of rows, filtered on read, no `visible`
  key list at all) would make this class of bug unrepresentable. Recorded as the follow-up
  in the change's `design.md`, deliberately not done here.
- No JS test harness exists in the repo, so nothing pins this against regression. The
  PostHog issue is the detector.
- Session replay is enabled; the original session id is
  `01a0b486-3e87-72a1-a94d-b8a0830e2610` if the recording is still in retention.
