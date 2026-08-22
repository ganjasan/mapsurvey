# Ranking question: drag items into a strict order

## Why

A respondent cannot be asked to put things in order. The platform has scales, and scales measure
something different: rating each item independently lets a respondent give two items the same
score, and averaging independent scores is not the same measurement as forcing a trade-off.

Two users asked; one is now blocking a launch on it:

- **Jannis Hamp (jhmp)**, 2026-08-14 and again 2026-08-15. He built the workaround himself — a
  `range` question named "Rating" whose five *choices* are the items to be ranked, which lets a
  respondent pick one item instead of ordering all five, and collects badly (5 answer rows, 1
  with a value). Offered per-item rating, he rejected it with the reason that settles this: he
  needs a **strict total order**, one unique rank per item per respondent, because ties destroy
  what he is measuring. He also considered and rejected pairwise comparisons himself — they admit
  intransitive answers (A>B, B>C, C>A). He has asked for a shipping estimate.
- **Manuel Frost (manu04)**, 2026-08-04, as one word in a list of nice-to-haves.

## What Changes

- **New input type `ranking`.** The creator lists the items (the existing choices editor); the
  respondent drags them into order. Every rank is used exactly once, because an invalid answer is
  not representable in the widget.
- **Storage reuses `Answer.selected_choices`** as an *ordered* list of choice codes — the
  respondent's permutation. **No migration.**
- **Uniqueness is enforced, not encouraged.** The server accepts a submission only when it is a
  permutation of the question's item codes; anything else stores nothing, the way an unanswered
  question stores nothing today. A widget that let a respondent type rank numbers would reproduce
  the tie problem, so there is no such widget.
- **Export gives one column per item**, valued by that item's rank — the shape that makes ranks
  analysable in a spreadsheet, and the shape the user asked for. This needs the export's
  one-question-one-cell contract widened to let a question contribute several columns.
- **Keyboard as well as pointer**: an item can be picked up and moved with the keyboard, so the
  question is not mouse-only.

Not in scope: a "rank only your top N" variant; ties by design (some instruments want them);
weighting; the analytics dashboard, which falls back to its answer-count view for the new type —
Jannis needs the export, and an honest count beats a chart that averages ranks without saying so.
Both are recorded as follow-ups.

## Capabilities

### New Capabilities

- `ranking-question`: what a ranking question asks of the respondent, what is stored, what is
  rejected, and how ranks leave the platform.

## Impact

- `survey/models.py` — `INPUT_TYPE_CHOICES` gains `ranking`.
- `survey/question_types.py` — picker metadata, so the type is discoverable (the failure that
  made Jannis build the workaround in the first place).
- `survey/forms.py` — `RankingField` / `RankingWidget`.
- `survey/templates/ranking.html`, `survey/assets/js/components/ranking.js`,
  `survey/assets/css/main.css` — the widget; collectstatic.
- `survey/views.py` — save path (validate the permutation), prepopulation, and `_answer_cell`
  plus the CSV assembly for multi-column export.
- `survey/tests.py` — permutation enforcement, ordering round-trip, export shape.
- Closes the ranking slice of backlog #102.
