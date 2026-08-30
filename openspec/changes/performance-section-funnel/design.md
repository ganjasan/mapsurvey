# Design: performance-section-funnel

## Counting

`SurveyEvent` rows carry `session_id` and `metadata.section_name`. `get_funnel()` reads
`values_list('session_id', 'metadata')` for `section_view` and `section_submit`, builds
`{section_name: set(session_ids)}` for each, and walks `_get_ordered_sections()`:

| field         | meaning                                                             |
|---------------|---------------------------------------------------------------------|
| `reached`     | distinct sessions with ≥1 `section_view` of the section              |
| `completed`   | distinct sessions with ≥1 `section_submit` of the section            |
| `reached_pct` | `reached / session_starts * 100`, rounded; 0 when no starts          |
| `dropped`     | `max(prev_reached - reached, 0)`; first step: `starts - reached`     |
| `dropped_pct` | `dropped / prev_reached * 100` (first step: over starts)             |
| `views`, `submits` | raw event counts, kept for the tooltip                          |
| `drop_rate`   | kept as before (event-based) so nothing else breaks                 |

Denominator is `session_start` count — the same number shown in the Sessions Started card, so the
first column is ≤100% and the card and the funnel agree. Sessions that viewed a section without a
`session_start` (older data) are still counted in `reached`; `reached_pct` is capped at 100.

## Rendering

Server-rendered HTML, no JS. Layout:

```
.perf-funnel            display:flex; gap; overflow-x:auto
  .perf-funnel-step     flex:1 1 0; min-width:140px
    .perf-funnel-bar    height:200px; hatched background (repeating-linear-gradient)
      .perf-funnel-fill position:absolute; bottom:0; height:{{reached_pct}}%; accent colour
    .perf-funnel-meta   step number badge + title (2-line clamp)
                        "→ N reached (x%)" green
                        "↘ M dropped (y%)" red, hidden when 0
```

Styles go into `survey/assets/css/editor-analytics.css` (or the stylesheet the analytics dashboard
already loads) — not inline, since the old partial's inline styles are what made it unreadable.
Chart.js stays loaded for the Charts tab; the funnel no longer uses it.

## Why not Chart.js

A funnel needs per-column captions with two coloured lines and a hatched remainder; Chart.js would
need plugins and custom tooltips for that and still render badly at 360px. Flex columns with
`overflow-x:auto` degrade gracefully on the phone screenshot that prompted this.
