## Context

`survey/layer_object_views.py` mutates a layer's objects from ten views. The create path
reads:

```python
key = _clean_key(payload.get('key') or '') or _next_key(layer)   # counts + reads all keys
if layer.items.filter(key=key).exists():                          # re-check
    return _error(...)
with transaction.atomic():                                        # only now a transaction
    obj = LayerObject.objects.create(layer=layer, key=key, ...)
    rebuild_layer(layer)
```

`_next_key()` takes `layer.items.count() + 1` and walks forward past taken keys. Both the
generation and the re-check sit outside the transaction, and no lock is held anywhere, so
two concurrent POSTs compute the same `o-2` and the second insert hits
`layerobject_unique_key_per_layer`. The `DETAIL` in the captured error names exactly that
key on a layer that already had objects.

Every other mutating view already opens `transaction.atomic()` and ends in
`rebuild_layer(layer)`, which recomputes the whole derived GeoJSON from `layer.items` and
saves it with `update_fields`. None of them lock either, which is the second defect: two
writers each rebuild from their own snapshot, and the last commit wins with a cache missing
the other's object. `check_object_caps(layer)` counts the same racy way, so two creates can
both pass a cap that only one of them should.

Constraints:

- `CLAUDE.md`'s layer-memory-diet rule: `SurveyMapLayer.geojson_gz` is up to 10 MB per row
  and a gunicorn worker keeps the resident memory of its largest request for life, so every
  editor path defers `GEOMETRY_TEXT_FIELDS`. `_layer()` already does. Anything new that
  touches the layer row must not undo that.
- The repo has no `TransactionTestCase` and no real threads in its suite — it stubs
  `threading.Thread` with an inline runner. A genuine race test would be the first of its
  kind against a shared test database.

## Goals / Non-Goals

**Goals:**

- No integrity error reaches a creator from concurrent object writes.
- The derived GeoJSON cache reflects every committed object, not the last writer's
  snapshot.
- The guarantee holds for every mutating path in the module, not only the one that was
  reported.

**Non-Goals:**

- Optimistic concurrency, queues, or advisory locks at the application level.
- Serialising anything beyond a single layer. Different layers, different surveys and
  respondent-side reads are untouched.
- `layers.py::sync_question_layers_for_session`, which materialises respondents' answers
  into `question`-sourced layers. Its keys are `s<session>-<n>` — already scoped to one
  session — and the object editor refuses those layers outright. Out of scope here; noted
  under Risks.

## Decisions

**A row lock on the layer, taken inside the transaction the view already opens.**

A small context manager in `layer_object_views.py`:

```python
@contextmanager
def _layer_write(layer):
    with transaction.atomic():
        SurveyMapLayer.objects.select_for_update().only('pk').get(pk=layer.pk)
        yield
```

and the mutating views wrap their whole read-modify-rebuild in it.

- **`.only('pk')`** rather than a plain `get()`: the lock needs the row, not its contents,
  and selecting the row unfiltered would pull `geojson_gz` into the worker — the exact thing
  the memory diet forbids. `.defer(*GEOMETRY_TEXT_FIELDS)` would work too; `.only('pk')`
  says the intent more plainly and cannot grow a new large column by accident.
- **The lock is the layer row, not the objects.** Locking the objects cannot work: the
  conflict is over a key that does not exist yet, so there is no row to lock. The layer row
  is the natural parent and is already loaded on every path.
- **Key allocation and the caps check move inside.** Leaving them outside would keep the
  bug — the lock would only protect the insert, which the database already protects.
- **`rebuild_layer()` stays inside.** That is deliberate and is what fixes the silent
  cache-loss half: the rebuild must see a state no other writer is changing underneath it.

Alternative considered — **catch `IntegrityError` and retry with a recomputed key**. It
avoids queueing and would also survive collisions from paths outside this module. Rejected
as the primary fix: it addresses only the key, leaving the rebuild race and the caps count
untouched, and a retry around a block that already wrote rows needs savepoint discipline to
avoid rebuilding twice. The lock fixes all three with one mechanism.

Alternative considered — **a unique-key sequence per layer (a counter column)**. Removes
the read entirely for key generation, but does nothing for the rebuild race, and adds a
migration plus a backfill for existing layers.

## Risks / Trade-offs

- **Writes to one layer now queue** → the editor is single-creator, so in practice the only
  queueing is a creator against their own second request. The slowest holder is an import,
  which already blocked the creator's own UI. Different layers are unaffected.
- **A long import holds the lock for its whole rebuild** → this is already the duration of
  its transaction; the lock does not extend it. If import duration becomes a problem it is
  a separate change about the rebuild, not about this lock.
- **Deadlock** → only one row is ever locked, in one order, so there is no lock-ordering
  cycle to create.
- **`sync_question_layers_for_session` still writes unlocked** → its keys carry the session
  id so a cross-session key collision is impossible, but its own `rebuild_layer()` can still
  lose a concurrent creator's write in the cache. Out of scope, called out here so it is not
  mistaken for covered.
- **A real race test may be flaky** → attempted on `TransactionTestCase` with two threads on
  separate connections; if it proves unstable against the shared test database it is dropped
  rather than kept, and the query-capture tests carry the regression guard. Whichever way it
  goes is recorded in `tasks.md`.

## Migration Plan

Pure server-side change, one module plus tests. No migration, no setting, no kill switch.
Ships with the normal deploy; rollback is reverting the commit.

## Open Questions

- None blocking.
