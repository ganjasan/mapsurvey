## ADDED Requirements

### Requirement: Section funnel counts sessions, not events

The Performance tab's Section Funnel SHALL report, for each section in survey order, the number of
distinct sessions that reached it (at least one `section_view`) and the number that completed it
(at least one `section_submit`). Repeated views by one session SHALL NOT increase the count.

#### Scenario: A session refreshing a section counts once
- **GIVEN** one session emitted three `section_view` events for section A and one `section_submit`
- **WHEN** the funnel is computed
- **THEN** section A shows `reached=1`, `completed=1`

#### Scenario: Percentages are relative to sessions started
- **GIVEN** 10 `session_start` events, 8 sessions viewed section A and 5 viewed section B
- **WHEN** the funnel is computed
- **THEN** A has `reached_pct=80`, `dropped=2`, `dropped_pct=20`; B has `reached_pct=50`,
  `dropped=3`, `dropped_pct=38` (3 of 8 that reached A)

#### Scenario: A later section reached by more sessions never shows negative drop
- **GIVEN** section A reached by 2 sessions and section B reached by 5
- **WHEN** the funnel is computed
- **THEN** B has `dropped=0` and `dropped_pct=0`

### Requirement: Section funnel renders as a step chart

The Section Funnel SHALL render one column per section with bar height proportional to
`reached_pct`, a visibly different fill for the unreached remainder, and under each column the step
number, section title, the reached count with percentage and — when non-zero — the dropped count
with percentage and, when `page_leave` data exists, the median time on the section. Below 768px
the steps SHALL stack vertically (horizontal bar per step) — the page SHALL NOT scroll
horizontally on a phone.

#### Scenario: Funnel markup
- **WHEN** the Performance tab is rendered for a survey with sections and events
- **THEN** the response contains one `.perf-funnel-step` per section, each with a
  `.perf-funnel-fill` whose inline height equals the step's `reached_pct`, and no `funnelChart`
  canvas
