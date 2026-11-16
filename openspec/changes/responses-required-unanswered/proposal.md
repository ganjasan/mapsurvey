## Why

The **Issues** column on Responses labels normal answers as defects, and creators act on the
labels by deleting real answers (#691). Over 60 days of production data, 75 % of answered
sessions carry at least one issue: "Incomplete" means "no answer in the last section" (57 %, and
625 of those reached the thank-you page), "Duplicate" means "same User-Agent within an hour"
(34 %), which since Chrome's User-Agent reduction catches different people on the same kind of
phone. 111 of the 308 respondent sessions trashed in that window were flagged Duplicate.

The same "answered the last section" rule defines **completed** on the Overview, the dashboard
cards, the export's `completed_only`, the REST summary and MCP. Creators do not care whether a
respondent reached the last page; they care whether the respondent answered what they marked as
required.

## What Changes

- **New marker "Required questions unanswered"**: a session gets it when at least one required
  top-level question of its version, visible to that respondent (the visibility engine decides),
  has no answer anywhere in the survey. Geo questions count by their minimum number of features,
  "Objects on the map" by `min_objects`. Rendered as quiet extra information (no red, no counter
  chip, no "issue" wording) with a tooltip naming the unanswered questions.
- **Keep "Shape edges cross"** (today's `self_intersection` lint) on the polygon answer, same
  quiet style, with a plain-language tooltip.
- **BREAKING (creator UI)**: remove the session issues Duplicate, Fast completion, Incomplete
  (last-section) and Missing required (section-scoped), and the per-answer warnings
  `numeric_outlier`, `short_text`, `area_outlier`, `out_of_range`, `empty_required` — from the
  table, the drawer, the map and the Overview.
- **BREAKING (creator UI)**: remove the Issues menu and the Issues chip; one on/off filter
  "Required questions unanswered" replaces them. Remove the Overview "flagged" KPI tile, the
  Responses-tab violations badge and the "Needs review" feed.
- Remove the settings that only fed removed rules: survey `fast_threshold_seconds`,
  `duplicate_window_hours` (and the validation-settings dialog); question `outlier_sigma`,
  `min_length`, `area_outlier_factor`. Old values in stored JSON are ignored.
- Number questions' **Min / Max** become a respondent constraint (owner decision 2026-11-16):
  until now they only fed the removed out-of-range warning and nothing enforced them.
- **BREAKING (definition)**: **completed** = not empty and no visible required question
  unanswered. One stored per-session flag feeds the Overview completion rate and trend, the
  dashboard cards, the export's `completed_only`, the REST summary's `completed` /
  `completion_rate` and MCP `get_response_summary`. A survey with no required questions counts
  every non-empty response as completed. Existing sessions are backfilled.
- Bulk delete states how many rows it will delete, whatever selected them.
- A "What's new" entry explains why the Issues column is gone, why completion rates change and
  that deleted responses can be restored from the trash.

## Capabilities

### New Capabilities
- `responses-required-unanswered`: the one definition of "required questions unanswered" /
  "completed" (stored per session, recomputed on every answer write, backfilled), the quiet
  marker and its tooltip, the filter, and the "Shape edges cross" note.
- `number-question-bounds`: Min / Max of a number question limit what a respondent can submit.

### Modified Capabilities
- `analytics-data-workspace`: the Issues chip and the per-type violation menu are removed; the
  toolbar gets the single "Required questions unanswered" filter; bulk delete states its count.
- `responses-overview`: the flagged KPI and the Needs-review feed are removed; completion rate
  uses the new definition.
- `responses-navigation`: the Responses pane item carries no violations badge.
- `responses-detail-drawer`: prev/next scenario no longer refers to the Issues filter.
- `responses-empty-sessions`: the "empty" issue no longer exists; the shared helper is used by the
  completion flag instead.
- `responses-export-formats`: `completed_only` uses the new definition.
- `rest-api-v1`: `completed` / `completion_rate` and `completed_only` use the new definition.
- `survey-editor`: dashboard card "completed" uses the new definition.
- `survey-service-layer`: `parse_validation_settings` no longer parses outlier sigma, text min
  length or polygon area factor.

## Impact

- Code: `survey/analytics.py` (`compute_session_issues`, `compute_answer_lints`,
  `completed_session_filter`, overview/dashboard stats), `survey/analytics_views.py`, the
  Responses v2 templates/JS (`_analytics_table_engine.html`, Overview, drawer, map),
  `survey/export.py`, `api/v1/responses.py`, MCP response tools, `survey/services/questions.py`,
  question modal and survey settings templates, ZIP serialization of `validation_settings`, the
  section POST and the paper-entry save path.
- Data: one new `SurveySession` column plus a data migration that backfills it.
- Generated docs: `help/…/reference/api.md`, `reference/mcp-tools.md` if the wording of
  "completed" changes; help pages that describe Issues.
- Numbers: completion rates change on most surveys (usually up); creators are told why in the
  What's new card. Personal follow-up to creators with Duplicate-flagged responses in their trash
  happens outside this repo.
