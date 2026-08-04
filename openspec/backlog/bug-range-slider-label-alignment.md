# Range slider: endpoint labels not aligned to the track, slider reads as too short

**Type**: bug
**Priority**: high
**Area**: frontend
**Created**: 2026-08-04

## Description

Follow-up on [Range slider: from-to labels](feature-range-slider-labels.md) (#5), which shipped.
The same user reports the result still does not read correctly:

1. **Labels are not at the endpoints.** `.range-labels` is laid out `justify-content: space-between`
   with no horizontal padding, while `.range-ticks` above it uses `padding: 0 10px`
   (`survey/assets/css/main.css:271-287`). The two rows therefore do not line up with each other.
   Neither lines up with the track: the native thumb is 22px wide, so the reachable extremes of the
   slider sit ~11px inside the element's box, and a label flush to the edge points at a position the
   thumb can never occupy.
2. **Only the first and last choice are labelled.** `RangeWidget.render` emits anonymous tick marks
   for the intermediate values and text for the endpoints only (`survey/forms.py:52-67`). On a
   9-point scale with named steps, seven of the names are invisible to the respondent.
3. **Slider reads as too short.** It is `width: 100%` of the question card, so this is a question-card
   width and spacing problem rather than a slider problem — worth reproducing at the widths a
   respondent actually sees before choosing a fix.

## Notes

- Reported by: Manuel Frost (manu04, Berlin Senate) 2026-08-04 — same user who requested #5. His
  surveys use 9-point scales such as "(positive) Geräusche" → "(negativer) Lärm".
- Fix 1 and 2 are small and independent. Fix 1 is alignment only. Fix 2 needs a display decision:
  labelling every step breaks down past ~5 points on a phone, so it probably means an opt-in
  "show all step labels" setting, or labels under the ticks with rotation on narrow screens.
- Reproduce at mobile width before committing to a layout — a 9-point labelled scale is the hard
  case, not the 5-point one.
- Related: [Additional scale question types](feature-additional-scale-question-types.md), which the
  same user asked for in the same message.
