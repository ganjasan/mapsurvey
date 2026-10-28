## Context

`survey/assets/js/layer_editor.js` keeps the object list in two pieces of state:

- `objects` / `byKey` — the rows, an array and a key→row map built from the same objects.
- `visible` — an array of keys: the rows that pass the current filter, in list order.

`recomputeVisible()` derives `visible` from `objects` and then calls `renderRows()`.
`renderRows()` is the only reader of `visible`, and it does:

```js
var o = byKey[visible[i]];
if (o.category) …          // first property read off o
```

So `visible` is an index into `byKey`, but nothing enforces that the two agree, and
`renderRows()` is reachable from four places that are not `recomputeVisible()`:
the `scroll` listener on the rows element, the `resize` listener on `window`,
`select()` and `closeCard()`.

Two windows where they disagree today:

1. **`reloadAll()`** (run after every CSV / GeoJSON / photo import) assigns `objects` and
   rebuilds `byKey` synchronously, then calls `loadGeometry()`, and only *that* — after a
   `fetch` of the layer GeoJSON, which for a large layer is megabytes — calls
   `recomputeVisible()`. For the whole round trip `visible` still holds the pre-import
   keys. A scroll or resize in that window throws from a plain event listener: uncaught,
   `handled: false`, which is exactly what PostHog captured.
2. **`removeLocal()`** deletes from `objects`/`byKey` and then, when the removed object is
   the selected one, calls `closeCard()` → `renderRows()` — before its callers
   (`loe-delete`, bulk delete) get to `recomputeVisible()`. That throw lands inside a
   promise `.then`, so the surrounding `.catch` turns a successful deletion into
   `status('error', …)` with the row still painted.

Constraints: this file is plain ES5-style browser JS with no build step and no JS test
harness in the repo (`CLAUDE.md` — template tests cannot see JS). Verification is by
driving the page in a browser, and by PostHog afterwards.

## Goals / Non-Goals

**Goals:**

- No uncaught exception from the object list, for any ordering of import, delete, scroll
  and resize.
- A deletion of the selected object reports success, not a spurious error.
- The invariant is restored where the state changes, not patched at the reader only — a
  defensive reader alone would hide the drift and paint a list missing rows.

**Non-Goals:**

- Rewriting the list into a single source of truth (one array of row objects, filtered on
  read). That is the structurally correct shape and would make the bug unrepresentable,
  but it touches every list function including the virtualisation, for a three-line defect.
  Noted as the follow-up if this area is opened again.
- Any change to imports themselves, the card, drawing, or the server side.
- Adding a JS test harness.

## Decisions

**Fix at both ends: restore the invariant at each mutation, AND make the reader tolerant.**

- In `reloadAll()`, call `recomputeVisible()` immediately after `features` is cleared and
  before `loadGeometry()`. `recomputeVisible()` walks `features` to restyle them, so it
  must run after `featureGroup.clearLayers(); features = {};`, not before — otherwise it
  styles layers that are about to be dropped. `loadGeometry()` ends with its own
  `recomputeVisible()`, which stays: the second pass is what styles the newly added
  features. The cost is one extra render of a list that is about to be re-rendered —
  cheap, and it is what removes the window.
- In `removeLocal()`, drop the key from `visible` before the `closeCard()` branch. Splicing
  the one key (rather than calling `recomputeVisible()`) keeps `removeLocal` cheap when the
  bulk path calls it in a loop over a selection; the callers still run one
  `recomputeVisible()` afterwards, which re-derives everything.
- In `renderRows()`, skip a position whose row is missing (`if (!o) continue;`). Chosen
  over `byKey[visible[i]] || {}`, which would paint an empty row where the creator expects
  data.

Why not the reader-only fix: with just the guard, an import would still repaint the list
from the *previous* import's key order for the length of a multi-megabyte fetch — silently
showing stale rows and dropping the new ones. The bug would stop being reported without
stopping.

Why not `Object.freeze`-style invariants or a state wrapper: disproportionate to a file
this size, and it would not survive the next direct assignment to `objects`.

## Risks / Trade-offs

- **The extra `recomputeVisible()` in `reloadAll()` renders a list whose features are not
  yet on the map** → `recomputeVisible()` calls `styleFeature(k, …)` only for keys in
  `features`, which is empty at that moment, so the loop is a no-op; the row markup itself
  does not depend on `features`. Verify by importing into a layer that already has objects.
- **Splicing `visible` in `removeLocal()` diverges from the "always re-derive" style of the
  rest of the file** → the callers still re-derive right after; the splice only closes the
  window inside `removeLocal` itself.
- **No automated test can pin this** → the regression would return silently. Mitigation:
  the PostHog issue is the detector — it is linked from the backlog item, and the tasks
  include re-checking it after the deploy. A JS test harness is out of scope here.
- **Hard to reproduce deliberately**, since window (1) is a network race → reproduce by
  throttling the network in devtools so the geometry fetch is slow, then scrolling.

## Migration Plan

Pure client-side change to one static asset. Ships with the normal deploy
(`collectstatic` re-hashes the file, browsers pick up the new name). No migration, no
setting, no kill switch — the rollback is reverting the commit.

## Open Questions

- None blocking. The single-source-of-truth refactor is recorded above as the follow-up,
  not as part of this change.
