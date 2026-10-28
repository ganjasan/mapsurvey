## 1. Fix the list state

- [x] 1.1 `renderRows()`: skip a position whose row is missing from `byKey` instead of
      dereferencing `undefined`
- [x] 1.2 `removeLocal()`: drop the removed key from `visible` before the `closeCard()`
      branch runs
- [x] 1.3 `reloadAll()`: call `recomputeVisible()` right after `featureGroup.clearLayers();
      features = {};` and before `loadGeometry()`
- [x] 1.4 Re-read the three functions together and confirm no other writer of `objects` or
      `byKey` leaves `visible` behind (`upsertRow`, the boot block, the bulk handlers)
- [x] 1.5 Found by 1.4 and fixed here: `reloadAll()` leaves `current` pointing at a key the
      import replaced, and the Delete button reads `byKey[current].title` — close the card
      when the selected object is gone

## 2. Verify in the browser

- [x] 2.1 Dev stack on `.env.ports` offset **360** (300 was already held by the py312
      worktree — the registry in `.env.ports.example` was stale and is now updated), seeded
      one survey with a 60-object layer
- [x] 2.2 CSV import of 40 objects with the geometry fetch delayed 6 s in the page, scrolled
      and resized 16 times across the window: zero uncaught errors, and the list read
      "of 95" from the first repaint — i.e. `visible` was already rebuilt, not left on the
      pre-import keys
- [x] 2.3 Selected an object and deleted it: status `saved`, count 60 → 59, row gone, zero
      uncaught errors
- [x] 2.4 Bulk-deleted four objects including the one open in the card: 59 → 55, card
      closed, all four rows gone, zero uncaught errors
- [x] 2.5 Unchanged paths re-checked: category chip, problem chip, search, prev/next,
      selection, and drawing a new object on the map (count 135 → 136, "Object added")

### Before-shot (the bug, on the pre-fix file)

- [x] 2.6 Same delete on `HEAD`'s `layer_editor.js`: the status bar read
      **"Cannot read properties of undefined (reading 'category')"** in the error style, the
      count stayed at 60 and the row stayed on screen although the server had deleted it
- [x] 2.7 Scrolling the list in that state raised
      **`Uncaught TypeError: Cannot read properties of undefined (reading 'category')`** —
      the exact message and the `handled: false` shape PostHog captured
- [ ] 2.8 Not reproduced from the *import* path on the pre-fix file: the control run's
      geometry fetch had already returned before the first measurement, so the window had
      closed. The mechanism is the same `renderRows()` read and is proven by 2.7; noting it
      rather than claiming a reproduction that did not happen

## 3. Land it

- [x] 3.1 `./run_tests.sh survey` — **OK, 2109 tests, 1 skipped, 634 s**, no failures or
      errors (no JS harness exists; this only guards against an accidental edit elsewhere)
- [ ] 3.2 Commit on `fix/layer-editor-category-typeerror`, open the PR, reference backlog
      item 184 and PostHog issue `01a0b4a5`
- [ ] 3.3 After the deploy, re-check the PostHog issue for new occurrences; mark it
      resolved there if the volume stops
