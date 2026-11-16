## Context

`data.dataviews` knows two kinds: `objects` (a layer's matching objects) and `grid` (cells of
distinct respondents over one geo question). `data.aggregate` holds the two privacy primitives,
`mask(count, k)` and `grid(members, k)`; `data.scope.SessionScope.public` is the set of sessions a
public number counts. `reports.render` still aggregates charts itself (moved there with the `/r/`
page in #703); the block set of #704 will read views instead.

The Responses page keeps its filter in the table's request parameters (`required`, `q`,
`cf_<column>`, `sort`, `dir`) plus `?version=`. Question columns are keyed by the database id of a
lineage's representative row, which changes when unpublished changes are published. The chart
"filters" of `filterManager` are not set by anything in the UI today; the timeline brush and
Hide / Keep only are client-side selections.

## Goals / Non-Goals

**Goals**
- Engagement, cross-tab, coverage and density as view kinds computed in `data`, tested there, read
  by the dataset page, REST and MCP.
- One privacy path: nothing a view returns bypasses `mask` / `grid`.
- A Responses filter saved as a `DatasetView` that survives publishing and re-opens the same table.

**Non-Goals**
- The reader: report blocks, charts and maps of these results are #704. The dataset page gets a
  plain preview (a table, three numbers, a cell summary).
- A kernel-density surface (#375) and exact, unmasked coverage counts for exports (#243).
- Scoping an analysis view by a saved Responses filter ("cross-tab of women over 60"). The filter
  is stored in a form that allows it; the resolver ships with the block that needs it.
- Moving `reports.render`'s chart aggregation into views — #704 replaces those blocks.

## Decisions

**1. Kinds are a table, `data.dataviews.KINDS_BY_DATASET`.** `kinds_for(dataset)` returns the
allowed kinds in order (the first is the default): layer → `objects`; answers → `grid`, plus
`coverage` for line/polygon or `density` for point/spraycan (the question is resolved by code);
responses → `engagement`, `crosstab`, `responses`. `clean()` refuses any other kind. A new kind is a
row there plus a function in `data.analysis`, never a branch in a view.

**2. `DatasetView.config` (JSON) carries kind-specific settings**, validated by `clean()`:
`crosstab` → `{"rows": code, "columns": code}`; `responses` → the filter state (decision 7); the
others → `{}`. `conditions` / `fields` stay what they were: an objects view's filter. Alternative —
overloading `conditions` — would make every reader guess the shape by kind.

**3. Engagement counts every clean session, not only external ones.** "Answered" must equal the
"N responses" every public surface prints (`SessionScope.public`), and that number includes the
workspace's own entries (operator entry, paper forms). Periods follow the collection span so a
two-year survey does not return 700 points: ≤ 45 days by day, ≤ 53 weeks by week, else by month,
in the server's time zone.

**4. Cross-tab: primary suppression plus withheld margins.** Cells are distinct respondents who
answered both questions; a cell in `0 < n < K` is masked. The total of every line holding a masked
cell is withheld — the total minus the visible cells returns one masked value, and pins two down
when they add up to 2 — and so is the grand total, because it and the other lines' totals return a
withheld total (found on the first real table: 112 − 33 − 21 − 3 gave the Bike row, and the row its
masked cell). What stays visible is then only sums of visible cells. Masking additional cells
(classic secondary suppression) would blank small tables and was rejected; losing the totals of the
affected lines is the cheaper price.
Questions allowed: top-level `choice`, `multichoice`, `rating`, `thumbs`. Numbers would need
binning rules (a v1.1 candidate); sub-questions are per feature, not per respondent.

**5. Coverage and density reuse `grid()`.** A line or polygon already counts in every cell it
touches, once per respondent — that is coverage; the view adds `share = respondents / everyone who
drew`. Density adds `marks`: `_bin` counts the point coordinates (points, spray dots) that fall in
each cell. The K rule stays on respondents: twenty marks from two people is still two people.
One binning seam, like the browser's `L.SprayAgreementLayer`.

**6. No unmasked reading.** Inside the workspace exact numbers exist on Responses and in the
export. A view is the thing that gets published, so its result is the published one for every
reader; the preview a creator sees is what the report will show. K is `k_for_survey` (the K of the
survey's report, else 3), as for grid views.

**7. A saved Responses view stores the table's parameters with question columns re-keyed by
code.** `config = {"version", "required", "q", "sort", "dir", "columns": {"<column>": "<cf
value>"}}` where a column is a meta key (`validation_status`, `tags`, …) or `q:<question code>`.
Saving translates `cf_<id>` → `q:<code>` through the lineage; opening translates back to the
current representative id. Choice filters keep the labels the table filters by today (`v:Car|Bike`)
— the table itself matches labels, and a second, code-based matcher would be a second filter
engine. Unknown codes are dropped on open (a deleted question filters nothing).
Not saved: the timeline brush, hidden rows, the selection, column visibility and trash mode — they
are momentary or per-browser.

**8. Opening is a parameter of the table, not client state.** `…/analytics/?view=<id>#responses`
loads the page; the first table request carries `view=<id>` and the server expands it into the
parameters before parsing, so the rendered `#table-state-form` holds the filter and every later
request repeats it. No second apply path in JavaScript.

**9. Saving needs the editor role** (the dataset edit rule, `services.can_edit`); every viewer can
open a saved view. Deleting goes through `services.delete_view`, which refuses a view a report
block uses.

**10. The question resolver moves to `data.questions`.** `reports.sources._questions_of` becomes an
import of `data.questions.questions_of`: Data must not import Reports to find a question.
(`data.dataviews._k_for` still reads the report's K; that dependency predates this change.)

## Risks / Trade-offs

- [A cross-tab of two multiple-choice questions is dense] → cells are respondents, not answers;
  the result flags `multiple` so a reader can say lines do not add up.
- [Choice filters by label break when a label is reworded] → same as the table today; the view
  shows fewer rows, never wrong ones. Noted in the help page.
- [Engagement on a huge survey loads every session's start time] → two id sets and one
  `(id, start)` list; 100k sessions is a few MB, computed on demand, not per page view.
- [`kind` widens from 8 to 12 chars] → `AlterField` on a small table.

## Migration Plan

`data/0008`: add `config`, widen `kind`. No data migration. Rollback: revert the commit; the column
is unused by older code.

## Open Questions

None blocking. For #704: whether a block may scope an analysis view by a saved Responses view.
