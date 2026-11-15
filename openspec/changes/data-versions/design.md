## Decisions

1. **The job, twice.** A version is a `DataImportJob` with `target` = the dataset. `run_data_version`
   runs in two modes: *preview* reads the file, computes the diff, stores counts in `report`, keeps
   the file and stops at status `preview`; *apply* (after the creator's confirm with a note) re-reads
   the same file and writes. The diff is recomputed at apply time, so an object edit between preview
   and apply is not overwritten blindly.
2. **Matching = the layer's `key_field`**, keys derived exactly as the import derives them
   (`layers.derive_key`, multi-part features suffixed `-n`). A row without a key value or with a key
   seen earlier in the file is skipped and reported. No key field on the layer → refused.
3. **In place.** A changed object keeps its `LayerObject` row (pk, key, assets, answers); title,
   geometry and properties are replaced. A removed object is deleted with its answers — the preview
   names how many answers that is. Added objects are appended after the last position.
4. **The field dictionary follows**: known names keep their labels/types/private flags; new columns
   come in with the import's profile (personal columns private).
5. **Caps**: the workspace's upload limit (`limits_for`), and — while the dataset is linked into a
   survey — the survey layer caps (5,000 objects / 10 MB after rebuild), checked at preview and at
   apply.
6. **History**: `DatasetVersion(dataset, number, note, created_by, created_at, added, changed,
   removed, unchanged)`; the upload creates number 1, a dataset from before shows "Original".

## Risks

- A 100,000-object diff holds the existing objects' keys, titles, properties and WKB in the worker
  for one job — bounded by the Pro limit.
