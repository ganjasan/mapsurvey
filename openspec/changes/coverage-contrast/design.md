## Context

`L.SprayAgreementLayer` draws both spray clouds (one member per session) and coverage (one member
per drawn shape since `responses-coverage-surface`). `_bin` increments `n` and the cell counts per
member, so shapes of one respondent add up. `_redrawGrid` maps a count to
`minAlpha + (maxAlpha - minAlpha) * count / n`.

## Decisions

### One respondent, one count: group members by id inside `_bin`
Members are grouped by `id` in input order; each group bins through one `seen` set that is cleared
between groups, so a cell gets at most one increment per respondent and memory stays one set.
`n` is the number of groups in scope. Spray is unaffected in practice (one cloud per session) but
gets the same guarantee.

### Opacity is one pure function
`L.SprayAgreementLayer.alphaFor(count, n, max, opts)` returns the cell alpha, or 0 for "not
drawn". Both the grid and the stats share it, the popover preview draws it, and it is testable
without a map.

- `scale: 'share'` (default, spray): `t = count / n`.
- `scale: 'max'` (coverage): `t = (count - floor) / (max - floor)` with `floor = max(1, minCount)`,
  and `t = 0` when `max <= floor`. The strongest cell in view is full colour, the weakest drawn
  cell is the minimum, a lone respondent paints a flat minimum surface as the original spec asks.
- `minCount`: cells with `count < minCount` are not drawn.
- `gamma`: `t' = t ^ gamma`, then `alpha = minAlpha + (maxAlpha - minAlpha) * t'`.

"Max" is the strongest cell IN VIEW, the same number the row already reports as "≤ N". Panning
to a weaker area re-stretches the scale, as leaflet.heat does on the point heatmap.

### Two knobs instead of a curve editor
The owner asked for creator control over the transition and floated an editable curve. A
draggable curve on a 250-px popover (and on a phone) is a lot of UI for what is, in practice, a
choice of "where does dark start". Two knobs cover it and keep the curve monotonic by
construction:

- **Contrast**, slider −100…100, `gamma = 4 ^ (value / 100)` (0.25…4). Right: only strong
  agreement is dark. Left: weak overlap becomes visible.
- **Minimum respondents**, slider 1…M: noise floor.

A 120×44 SVG under the sliders plots alpha against respondent count 1…max for the current
settings, so the knob's effect reads before the map redraws. A free-form curve can later be
added as a third mode over the same `alphaFor` seam.

### Coverage reaches 0.9, not 0.75
Spray's 0.75 ceiling was tuned for clouds over a street map. A coverage colour over open water
or forest at 0.75 still reads pale, so coverage passes `maxAlpha: 0.9`. The cell slider's maximum
follows the automatic cell (twice it, rounded up to a kilometre, never below 1 000 m): a
region-wide source gets cells of several kilometres, and a slider that stops at 1 000 m showed
its thumb pinned at the end with a value it could not represent.

### Not persisted
Coverage slots are not recreated on reload (existing spec), so their settings are not either.

## Risks

- Relative scaling hides absolute agreement level: a map where the strongest cell has 3 of 21
  looks as dark as one with 20 of 21. The row's "≤ N of M respondents" stays the honest number,
  and the curve preview labels its axis with the real counts.
