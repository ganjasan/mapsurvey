## ADDED Requirements

### Requirement: Section funnel separates rule-skipped respondents from dropped ones

For a section carrying a valid visibility rule, the Section Funnel SHALL report `eligible` (distinct
sessions that reached the baseline step and answered the controlling question with a matching
option), `skipped` (baseline reached minus eligible) and `dropped` (eligible minus reached, never
negative). `dropped_pct` of such a step SHALL be relative to `eligible`. The baseline step is the
nearest earlier section without a valid rule, or the session starts when there is none. A section
whose rule is broken SHALL be treated as unconditional.

#### Scenario: Skipped respondents are not dropped
- **GIVEN** 10 sessions started, all 10 viewed section A, 7 answered A's choice question with the
  option that shows section B, and all 7 viewed B
- **WHEN** the funnel is computed
- **THEN** B has `eligible=7`, `skipped=3`, `dropped=0`, `dropped_pct=0`, `reached_pct=70`

#### Scenario: A loss inside a branch is measured against the eligible
- **GIVEN** the same survey but only 5 of the 7 eligible sessions viewed B
- **WHEN** the funnel is computed
- **THEN** B has `eligible=7`, `skipped=3`, `dropped=2`, `dropped_pct=29`

#### Scenario: A broken rule falls open in the funnel
- **GIVEN** section B's rule references a question code that no longer exists
- **WHEN** the funnel is computed
- **THEN** B is reported with `conditional=false`, `rule_broken=true`, and its counts follow the
  unconditional formulas

### Requirement: The step after a branch compares with the last unconditional step

The `dropped` count of a section that follows one or more conditional sections SHALL be computed
against the reached count of the nearest earlier unconditional section, and the payload SHALL name
that step (`baseline_step`) so the caption can say which step it compares with.

#### Scenario: A branch does not inflate its successor
- **GIVEN** section A reached by 10 sessions, conditional section B reached by 7, section C reached
  by 10
- **WHEN** the funnel is computed
- **THEN** C has `dropped=0`, `baseline_step=1` (A) and B has `baseline_step=1`

#### Scenario: A real loss after a branch is still visible
- **GIVEN** section A reached by 10, conditional B reached by 7, section C reached by 8
- **WHEN** the funnel is computed
- **THEN** C has `dropped=2`, `dropped_pct=20`, `baseline_step=1`

### Requirement: Conditional steps are legible in the step chart

A conditional step SHALL render with a branch badge reading "Shown when <controlling question> =
<options>" (the same wording the editor structure pane uses), a visibly distinct bar frame, a light
band above the fill sized to the skipped share of started sessions, a "skipped by rule" line in
place of a dropped line when nothing was dropped, and — when something was dropped — the dropped
line labelled as a share of the eligible. A step whose baseline is not the immediately preceding
step SHALL say "since step N" on its dropped line. The chart SHALL carry a legend for the three
fills. A broken rule SHALL render the editor's warning badge with its reason. Below 768px the band
SHALL render on the horizontal bar.

#### Scenario: Conditional step markup
- **WHEN** the Performance pane is rendered for a survey where section B has a valid rule and 3 of
  10 sessions were skipped by it
- **THEN** B's column has the `is-conditional` class, contains the badge text "Shown when", a
  `.perf-funnel-skipped` band whose inline height equals 30%, the text "3 skipped by rule" and no
  "dropped" line

#### Scenario: Successor caption names the baseline
- **WHEN** the pane is rendered for A → conditional B → C with C reached by fewer sessions than A
- **THEN** C's dropped line contains "since step 1"

#### Scenario: Broken rule badge
- **WHEN** the pane is rendered for a section whose rule is broken
- **THEN** its column carries the warning badge and no `.perf-funnel-skipped` band
