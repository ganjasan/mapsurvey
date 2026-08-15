# Design — range renders as a slider, only

## Context

`resolve_display_style` already funnels every non-`DISPLAY_STYLE_TYPES` type to `'default'`, and
the range field builder only takes the choice-based path when the resolved style asks for it. So
the decoupling is subtractive: shrink the type list, delete the branch, and the existing
fallbacks do the rest — including for the two production range questions that have `list_pips`
stored.

## Decisions

### D1 — Ignore stored styles rather than rewriting them

`display_style` values already stored on range questions stay in the DB and are simply never
consulted (range resolves to `'default'` before the stored value is read). Rationale: identical
to how the feature treated its own no-choices fallback; no prod data mutation, instantly
revertible, and a future scale-type merge (#102) can still read the old values if it wants them.

### D2 — Contract shrinks on both sides at once

`SurveySectionAnswerForm.DISPLAY_STYLE_TYPES` and the modal's JS `DISPLAY_STYLE_TYPES` both go to
rating-only in the same commit — the template comment already binds them ("keep the two in
step"). The "Display as" block itself is untouched; it simply never shows for range again.

### D3 — Tests assert the new invariant against the old fixtures

`RangeDisplayStyleTest` keeps its nine-point named-scale fixtures but flips the expectation:
whatever `display_style` is stored, the render is the slider, storage stays `numeric`,
prepopulation works, and rating's survey-default inheritance is unchanged. The live-preview
endpoint is asserted too: posting `display_style=list_pips` with `input_type=range` renders the
slider — the editor cannot even preview the removed combination.

## Risks / Trade-offs

- The nine-point named-scale readability problem returns for range questions — by design: the
  answer is now "that is a rating question", and the picker's hints, examples and live preview
  exist to route creators there. The two affected prod questions are one user's (jhmp), whose
  case is exactly that.
- Stacked branch: merges after PR #60; GitHub retargets to master automatically.

## Migration Plan

Code-only, no data steps. Revert = revert the commit; stored styles were never cleared.
