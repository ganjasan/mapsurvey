## Why

After moderation infrastructure (#40-#42), researchers can manually review and status sessions. But with 500+ responses, they need automated detection of problematic sessions: empty submissions (bots/accidental clicks), incomplete surveys (abandoned mid-way), and missing required answers (client-side validation bypassed or skipped).

## What Changes

- New `compute_session_issues()` method on `SurveyAnalyticsService` computing 3 rules per session via bulk queries
- "Issues" system column in attribute table with color-coded badges (Empty, Incomplete, Missing required)
- Dropdown filter to show only sessions with specific issue types
- "Flagged" count in overview stat cards
- No automatic status changes — flags are advisory only

## Capabilities

### New Capabilities
- `auto-validation-basic`: On-the-fly detection of empty, incomplete, and missing-required sessions displayed as advisory flags in the attribute table

### Modified Capabilities
- `get_table_page`: New "issues" system column + issues filter
- `get_overview`: New `flagged_count` in overview stats
- `analytics_table.html`: Issues column rendering + filter dropdown
- `analytics_overview.html`: Flagged stat card

## Impact

- `survey/analytics.py` — `compute_session_issues()` method, `get_table_page()` and `get_overview()` changes
- `survey/analytics_views.py` — `issues` filter param, pass to template
- `survey/templates/editor/partials/analytics_table.html` — issues column, filter dropdown
- `survey/templates/editor/partials/analytics_overview.html` — flagged stat card
- `survey/tests.py` — tests for all 3 rules
