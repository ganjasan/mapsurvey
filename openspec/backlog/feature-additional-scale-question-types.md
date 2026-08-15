# Additional scale and ranking question types

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-08-04

## Description

The current scale offering is one discrete horizontal slider (`range`) plus radio-button `rating`.
Researchers used to standard survey tools expect more:

- **continuous scale** — a visual analogue scale with no discrete steps, storing a float rather
  than a choice code (`Answer.numeric` already accommodates this)
- **vertical scale** — same data, rotated; the natural orientation for a long labelled scale on a
  phone, and the standard presentation for some instruments
- **ranking** — order N items by preference, which no current type approximates
- **presentation variants** for the existing types — stars, numbered buttons, faces, segmented bars
  instead of a single slider style

## Notes

- Asked for by: Manuel Frost (manu04, Berlin Senate) 2026-08-04 — "It would be nice if you can
  implement more and different Input types (continuous scale, vertical scale, ranking, different
  styles)." Framed by him as nice-to-have, but he is the second user to push on scale rendering.
- Split before scheduling; these are three different sizes of work. Presentation variants of
  `range`/`rating` are styling and belong with
  [range slider label alignment](bug-range-slider-label-alignment.md). Continuous and vertical
  scales are new widgets over existing storage. Ranking needs a new answer shape, export handling
  and analytics — treat it as its own change.
- **2026-08-05 — the "different styles" slice is done**, in change `range-scale-display`: `range`
  questions now offer the same per-question "Display as" choice `rating` has, so a creator can pick
  the slider, a compact scale strip, or a labelled list showing every step's name. Storage is
  unchanged in all three.
  Still open here: **continuous** (non-stepped) scale, **vertical** scale, and **ranking**. The
  first two are new widgets over the existing numeric storage; ranking needs a new answer shape and
  is the only one of the three that touches export and analytics.
- The display-style machinery now dispatches on `SurveySectionAnswerForm.DISPLAY_STYLE_TYPES`, so
  adding a style is an entry there, a partial, and a thumbnail in the editor's picker — not a new
  branch in the template.
- Every new type has to be carried through the export path and the analytics aggregation, not just
  the form. The export function currently drops unhandled types silently — see
  [datetime missing from CSV export](bug-datetime-missing-from-csv-export.md).
- Related: [Budget/token allocation question type](feature-budget-token-allocation.md) (#17), which
  is the same family of "distribute or order a fixed set" input.
- **2026-08-10 — partially shipped.** Only the display-style slice landed (`survey/forms.py:175` `DISPLAY_STYLE_TYPES`, `survey/models.py:117`). Continuous scale, vertical scale and ranking are still absent from `INPUT_TYPE_CHOICES`.
- **2026-08-14 — second ranking request.** Jannis Hamp (jhmp, private survey, found us via
  Google) asked for exactly the ranking type: "give a number of answers which the participants
  have to order according to a scale … from 1 (best) to 5 (worst)". Two independent requests
  in ten days (Manuel Frost 2026-08-04, Jannis Hamp 2026-08-14).
  **Correction, same day:** Jannis's actual example ("how much do you like each fruit, 1–5") is
  coverable today with one `rating` question per item — his request is at least partly a
  discoverability failure of the flat type picker, not a missing capability. Logged against
  [rework the question type picker](improvement-group-question-type-list.md). True drag-to-order
  ranking (strict ordering, one answer shape) remains open here.
