## Why

Creating an object in the layer editor is a read-check-write with nothing holding a lock,
so two concurrent creates in the same layer both pick the key `o-2`, both pass the
existence check, and the second insert dies on the unique constraint — a 500 in the
creator's editor (PostHog issue `01a0abb4`, 2026-09-16, backlog
`bug-layer-object-key-collision.md`).

The missing lock has a second, quieter consequence found while reading the module. Every
mutating view ends in `rebuild_layer(layer)`, which recomputes the whole derived GeoJSON
from `layer.items`. Two writers each recompute inside their own transaction, each seeing
only their own insert, and whoever commits last writes a cache that is **missing the other's
object** — until some later write rebuilds it again. That one produces no error and no log
line: an object silently absent from the map respondents see.

## What Changes

- Writers of one layer are serialised: the mutating paths in `survey/layer_object_views.py`
  take a row lock on the layer before reading what they are about to write, and hold it
  through the rebuild of the derived GeoJSON.
- Key allocation, the object caps check, the insert and `rebuild_layer()` move inside that
  one transaction, instead of straddling its edges.
- Applies to every mutating path in the module — object create, patch, delete, bulk
  actions, asset add/delete/reorder, and the GeoJSON, CSV and photo imports. They already
  open `transaction.atomic()` and already end in `rebuild_layer()`; none of them lock.
- The lock never loads the layer's GeoJSON text, per the layer-memory-diet rule.
- No change to any response body, URL, permission or model.

## Capabilities

### New Capabilities
- `layer-object-writes`: what a creator is guaranteed when objects in one reference layer
  are written concurrently — that a generated key is unique, that the caps are counted
  against what is really there, and that the derived GeoJSON cache reflects every committed
  object. Scoped to write serialisation; what each endpoint does on its own is unchanged and
  stays undocumented here.

### Modified Capabilities

## Impact

- `survey/layer_object_views.py` — one new helper plus the mutating views adopting it.
- Concurrency: writes to the **same** layer now queue behind each other for the duration of
  a rebuild. Different layers and different surveys are unaffected. The editor is a
  single-creator surface, so the queueing is not expected to be observable; the imports are
  where a rebuild is slowest.
- `survey/tests.py` — query-capture tests that the lock is taken and that it does not select
  the GeoJSON column.
- No template, model, migration or setting. Rollback is reverting the commit.
