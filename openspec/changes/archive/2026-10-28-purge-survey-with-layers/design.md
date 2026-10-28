## Context

`purge_survey(survey)` (`survey/trash.py`) is the one routine behind both Delete-forever
and the scheduled auto-purge. It builds the family of headers to remove — the survey, its
archived versions (`canonical_survey=survey, is_canonical=False`) and its live draft copy
(`published_version=survey`) — cleans media, deletes sessions explicitly, then deletes the
headers in reverse order so the canonical goes last.

Two PROTECTed FKs sit in that path:

| FK | on_delete | Handled today |
|---|---|---|
| `SurveySession.survey` | PROTECT | yes — explicit delete before the headers |
| `Question.layer` → `SurveyMapLayer` | PROTECT | **no** |

`SurveyMapLayer.survey` is CASCADE, and `LayerObject.layer` is CASCADE, so the rows would
disappear on their own — if the collector ever got that far. It does not: Django's
`Collector` evaluates PROTECT during collection, not during deletion, and does not exempt
an object that is itself being collected. So a survey owning a layer that any question is
bound to cannot be deleted at all.

## Goals / Non-Goals

**Goals**

- Delete-forever completes for a survey that owns layers, removing layers, their objects
  and their attachments.
- One failing survey does not abort an auto-purge run.
- The creator sees what the purge will take before confirming.

**Non-Goals**

- Changing `Question.layer`'s PROTECT. On the Reference layers card it is the right
  behaviour and it is specified (`reference-overlay-layers`): deleting a bound layer must
  refuse and name the question.
- Repairing the nine surveys already stuck in Trash. They are stuck on data, not state;
  once this ships, their buttons work. Nothing to backfill.
- Touching `layers_for()` / `layer_owner()` borrowing. Drafts and versions borrow the
  canonical's layers, and those headers are already in the purge family.

## Decisions

### D1 — Clear the PROTECT by deleting the questions' layer binding, not the questions

Two ways to get past `Question.layer`:

1. `Question.objects.filter(...).delete()` before the layers.
2. `Question.objects.filter(...).update(layer=None)` — the field is `null=True`.

Take (2). Deleting questions first would work, but it makes `purge_survey()` responsible
for a second cascade (answers, sub-questions, `Answer.layer_object`) whose order is already
handled correctly by the header cascade. Nulling the FK is one UPDATE that removes the
only obstacle and leaves the existing cascade to do exactly what it does today. The rows
are being deleted seconds later; a transient `layer=NULL` is never observed.

Scope the update through the header family, not the layer: a question in a survey that is
*not* being purged must never have its binding cleared. Production has zero such bindings
today (verified: 30 apparent cross-survey bindings are all drafts borrowing their own
published survey's layer, and every one of those headers is inside the purge family), but
the query is written to be correct rather than to match today's data.

### D2 — Delete layers explicitly, mirroring the session handling

After the binding is cleared, `SurveyMapLayer.objects.filter(survey__in=headers).delete()`
takes the layers and, by CASCADE, their `LayerObject`s and `LayerObjectAsset` rows. This
could be left to the header cascade, but doing it explicitly keeps the routine readable as
"everything PROTECT-adjacent, in order, then the headers" and puts the delete next to the
asset cleanup that has to precede it.

### D3 — Asset files come off storage before the rows

`LayerObjectAsset` files live on the public media tier under random `layer_assets/<uuid>`
keys. The existing routine already deletes cover images and question images through the
storage API precisely because the DB cascade only removes references. Attachments get the
same treatment, in the same media-cleanup block.

Production has zero `LayerObjectAsset` rows, so this ships untested against real data —
which is the reason to write it now rather than after the first customer with photo
batches purges a survey.

### D4 — A failing survey is skipped, not fatal, and the failure is recorded

`purge_expired_surveys()` loops over expired surveys and calls `purge_survey()`. Today one
exception ends the run. Wrap the per-survey call so a failure is logged and counted, and
the loop continues.

Deliberately NOT a bare `except Exception: pass`: the return value grows to report
failures, the logger records the survey and the exception, and the internal endpoint's
response says how many failed. A purge that cannot complete must be visible — the whole
reason this bug survived two days of retries is that the failure was only visible in
PostHog.

The audit row stays where it is: written before the purge attempt, as now. An audit line
for a purge that then failed is the lesser evil against a purge with no audit line at all.

### D5 — The dialog names layers and objects, and never blocks

The Delete-forever modal gains one line when the survey owns layers: "Including N
reference layers with M objects." No new confirmation step, no checkbox. The creator
already passed Trash and a red irreversible-action dialog; a third gate would be
cargo-culted safety.

Counting happens where the trash list is built, as one aggregate per owner rather than a
query per row.

## Risks / Trade-offs

- **A draft copy borrowing a layer.** If the draft is in the family (it always is — it is
  found by `published_version=survey`) its questions' bindings are cleared with the rest.
  Covered by a test that purges a survey with a live draft copy.
- **`update(layer=None)` on a large survey.** One UPDATE over the questions of a header
  family; the largest production survey has 220 layer-bound questions across all surveys
  combined. Not a concern.
- **Someone re-adds a PROTECT FK to `SurveyHeader` later.** The same class of bug returns.
  The test added here asserts the purge completes for a survey with layers; it will not
  catch a third PROTECT. A generic "purge a maximally-populated survey" test is the real
  guard — the fixture in this change is built to be extended into one.

## Migration Plan

None. Behaviour-only change; no schema, no data repair. The nine stuck surveys start
purging correctly the moment this deploys, either from the button or from the scheduled
job.

## Open Questions

None blocking. One to revisit later: `purge_expired_surveys()` now reports failures, but
nothing alerts on them. The internal endpoint's response is read by a curl cron that
discards its body. Out of scope here; worth a backlog item.
