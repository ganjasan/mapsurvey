## 1. The lock

- [x] 1.1 Add the `_layer_write(layer)` context manager to `survey/layer_object_views.py`:
      `transaction.atomic()` plus `select_for_update().only('pk')` on the layer row
- [x] 1.2 `objects_collection` POST: move key allocation (`_next_key`), the taken-key check
      and `check_object_caps` inside it, alongside the insert and `rebuild_layer`
- [x] 1.3 Adopt it in the remaining mutating views: `object_detail` PATCH/DELETE,
      `object_geometry`, `objects_bulk`, `asset_create`, `asset_detail` DELETE,
      `assets_reorder`
- [x] 1.4 Adopt it in the three imports: `import_geojson` (caps moved inside too),
      `import_csv`, `import_photos`
- [x] 1.5 Swept the module: every `rebuild_layer()` now runs under the lock except
      `layer_create_empty`, which rebuilds a layer it has just created and that no other
      request can see yet. Two decisions worth recording:
      - the **uploads stay outside** the lock — `asset_create` writes its file to the media
        tier (an S3 round trip) and `import_geojson` parses up to 10 MB before it locks;
        the rows they write are committed before the rebuild reads them
      - `layer_create_empty` races on `MAX_LAYERS_PER_SURVEY` between *different* layers of
        one survey. Real, but a different lock object (the survey) and a different defect;
        not touched here

## 2. Tests

- [x] 2.1 Query-capture: creating an object issues `FOR UPDATE` against the layer row
- [x] 2.2 Query-capture: that locking query does not select `geojson_gz`
- [x] 2.3 Generated keys skip the ones already taken, including a layer whose keys have gaps
- [x] 2.4 A supplied key that is taken still returns 400 naming the key, not a 500
- [x] 2.5 `test_every_mutating_path_locks` — added beyond the plan: patch, geometry, bulk
      and delete each asserted to lock, so a future endpoint that forgets is caught
- [x] 2.6 **The genuine race test lives** (`LayerObjectWriteRaceTest`, `TransactionTestCase`):
      two threads on two connections, rendezvousing inside key allocation. It reproduces
      the production failure verbatim when the lock is removed —
      `duplicate key value violates unique constraint "layerobject_unique_key_per_layer",
      DETAIL: Key (layer_id, key)=(1, o-4) already exists` — and passes with it. Ran 5×
      in a row: 5 green, not flaky.
      A first attempt at this test was **wrong and was rewritten**: it held the layer row
      from the test's own transaction and asserted the writer blocked. It passed with the
      lock removed, because an unlocked writer still blocks on the `UPDATE` that
      `rebuild_layer` issues against the same row. A test that cannot fail proves nothing.
- [x] 2.7 Verified the guards fail without the fix: with the lock neutered,
      `test_creating_an_object_locks_the_layer_row` and all four subtests of
      `test_every_mutating_path_locks` fail, and the race test fails with the integrity
      error above
- [x] 2.8 Full `./run_tests.sh survey` — **OK, 2115 tests, 1 skipped, 637 s**, no failures.
      (The first attempt reported 825 errors, all
      `ValueError: Missing staticfiles manifest entry for 'img/maki.svg'`: I had skipped
      `collectstatic` when setting the worktree up, and the storage backend is
      `CompressedManifestStaticFilesStorage`, so every template using `{% static %}` raises.
      Nothing to do with this change; recorded because the failure mode points squarely at
      whatever code is under test.)

## 3. Land it

- [ ] 3.1 Commit on `fix/layer-object-key-collision`, open the PR, reference backlog 185 and
      PostHog issue `01a0abb4`
- [ ] 3.2 After the deploy, re-check that PostHog issue for new occurrences and resolve it
      there if the volume stops
