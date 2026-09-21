# Creating layer objects races on the generated key and 500s with an IntegrityError

**Type**: bug
**Priority**: medium
**Area**: backend
**Created**: 2026-09-21
**Status**: fixed — change `serialise-layer-object-writes`

## Description

PostHog captured `IntegrityError: duplicate key value violates unique constraint
"layerobject_unique_key_per_layer", DETAIL: Key (layer_id, key)=(139, o-2) already exists.`
from `survey/layer_object_views.py` on 2026-09-16. One occurrence, one creator — a 500 in
the object editor while adding objects to a layer.

`_next_key()` reads the layer's existing keys and picks the first free `o-<n>`; the create
view then re-checks with `layer.items.filter(key=key).exists()` and only afterwards opens
the transaction and inserts. Read, check, write — with nothing holding a lock between them.
Two concurrent POSTs (a double click, or drawing two objects in quick succession over a slow
connection) both compute `o-2`, both pass the existence check, and the second insert hits
the unique constraint. The `DETAIL` naming `o-2` on a layer that already had objects is
exactly that shape.

[PostHog issue](https://eu.posthog.com/project/248938/error_tracking/01a0abb4-7d2a-7350-a8be-722946ae79b1)

## Proposed Approach

Make key allocation atomic rather than advisory. Options, cheapest first:

- Move `_next_key()` + the insert inside one `transaction.atomic()` with
  `SurveyMapLayer.objects.select_for_update().get(pk=layer.pk)` at the top, so concurrent
  creates on the same layer serialise.
- Or keep the optimistic path and catch `IntegrityError` around the `create()`, retrying
  with a recomputed key a bounded number of times.

Either way the creator should never see a 500: on exhaustion return the existing
`_error('An object with key … already exists in this layer.')` JSON the editor already
renders through `status('error', …)`.

## Confirmed and fixed (2026-09-21)

Reproduced in a test: two threads on two connections creating an object in one layer,
meeting inside key allocation, produce exactly the reported failure —
`duplicate key value violates unique constraint "layerobject_unique_key_per_layer",
DETAIL: Key (layer_id, key)=(1, o-4) already exists`.

Reading the module turned up a **second, quieter consequence of the same missing lock**.
Every mutating view ends in `rebuild_layer(layer)`, which recomputes the layer's whole
derived GeoJSON from its objects. Two writers each rebuild inside their own transaction,
each seeing only their own insert, so whoever commits last stores a cache that is *missing
the other's object* — no error, no log line, just an object absent from the map respondents
load until some later write rebuilds it. `check_object_caps` counts the same racy way.

Fixed by serialising writers of one layer: `_layer_write()` takes `SELECT ... FOR UPDATE` on
the layer row (via `.only('pk')`, so it never loads `geojson_gz`) and every mutating path in
`layer_object_views.py` does key allocation, caps, the write and the rebuild inside it.

## Notes

- `_next_key` is also called from the CSV import path (`survey/layer_object_views.py:484`),
  which builds keys in a loop inside one request — that path is not racing with itself but
  would benefit from the same lock if an interactive create runs alongside an import.
- `rebuild_layer(layer)` runs inside the same transaction, so a retry must not rebuild twice.
- Found in the PostHog error-tracking sweep of 2026-09-21 together with
  `bug-layer-editor-category-typeerror.md`.
