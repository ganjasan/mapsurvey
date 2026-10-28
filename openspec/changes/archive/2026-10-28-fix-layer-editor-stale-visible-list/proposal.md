## Why

The layer object editor throws an uncaught `TypeError: Cannot read properties of undefined
(reading 'category')` at creators mid-edit — three times in one session on 2026-09-18
(PostHog issue `01a0b4a5`, backlog `bug-layer-editor-category-typeerror.md`). The list of
objects keeps its filtered order in `visible` (an array of keys) and its data in `byKey` (a
map), and the two are allowed to drift apart. `renderRows()` reads `byKey[visible[i]]` and
touches the result with no check, so a key that is in the order but no longer in the map
kills the render.

The widest drift window opens right after an import — exactly when the list has the most to
show — and the throw arrives from a scroll or resize listener, so nothing catches it and the
creator is left with a half-painted list and no message.

## What Changes

- `reloadAll()` recomputes the visible order at the moment it replaces `objects`/`byKey`,
  instead of leaving the previous import's keys in place until the layer GeoJSON fetch
  returns.
- `removeLocal()` drops the deleted key from the visible order before `closeCard()` can
  repaint, so a deletion of the selected object no longer renders a row whose data is gone.
- `renderRows()` skips a key with no row behind it rather than dereferencing `undefined`,
  so any future desync degrades to a missing row instead of an uncaught exception.
- No change to what the editor shows, what it saves, or any server endpoint.

## Capabilities

### New Capabilities
- `layer-object-editor`: the object editor's list state — the invariant between the visible
  order and the object rows behind it, and what the creator sees while the editor reloads
  its objects after an import or a delete. Scoped to list-state consistency; the rest of the
  editor's behaviour (drawing, the card, imports themselves) stays undocumented here and
  unchanged.

### Modified Capabilities

## Impact

- `survey/assets/js/layer_editor.js` only — three functions (`renderRows`, `removeLocal`,
  `reloadAll`). No template, view, model or migration touched.
- Surfaces: the object editor page `/editor/surveys/<uuid>/layers/<id>/edit/`. Respondent
  and Responses surfaces read layer GeoJSON through their own code and are unaffected.
- Static assets: the file is served through `collectstatic`, so the change ships with the
  usual hashed-name rebuild and nothing else.
