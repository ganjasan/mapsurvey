## Why

Most sessions in Responses carry no answer at all: a respondent opened the survey and left. Over the
30 days before 2026-10-02, 1794 of 2529 external sessions on production (71%) had no answer, and the
Responses page shows each of them as a row equal to a real response. Creators grind through the
delete button to clean the table (one deleted 63 rows in two minutes on 2026-08-26), and a studio
running the biggest live consultation on the platform could not tell how many people actually
responded: the headline said 350, the real number was 146 (issue #226).

## What Changes

- **Empty session** gets one definition, shared by every surface: a session with no top-level
  `Answer` row (`parent_answer_id IS NULL`). Answers about layer objects and moderator-hidden
  answers count as answers. This is the rule the existing `empty` issue already uses.
- **Responses** (table, Overview, Map, Charts): empty sessions are hidden by default. The page
  states both numbers, e.g. "146 responses · 204 opened without answering", and a toggle shows the
  empty sessions again. Nothing disappears silently. The choice is remembered per browser.
- **Export** (legacy archive, Excel, CSV, GeoPackage, Shapefile, KML): empty sessions are never
  exported. They hold no answer, so every format loses only blank rows.
- **Overview "Needs review"** no longer lists empty sessions while they are hidden: an empty session
  is not something to review, and today it floods the feed.
- **Section POST** strips whitespace-only text before the existing blank filter, so `"   "` no longer
  creates an `Answer` row that makes a session look non-empty.
- **Unchanged**: the funnel and Perf pane (`SurveyEvent`), where "opened" is the point; individual
  answers inside a shown session; trash and validation statuses; per-row delete. No bulk delete.
- **Unchanged, by decision**: 15 legacy sessions whose only answers are blank rows written before
  2026-08-25 stay visible. No data migration.

## Capabilities

### New Capabilities
- `responses-empty-sessions`: the definition of an empty session, the default that hides them on the
  Responses page, the two-number headline and the toggle that shows them.

### Modified Capabilities
- `responses-overview`: KPIs and the Needs-review feed are computed over the shown sessions; the
  scenario that lists an empty session in Needs review changes.
- `responses-export-formats`: every format leaves empty sessions out, regardless of
  `include_all` and `completed_only`; the legacy archive's CSV loses its blank rows too.
- `analytics-data-workspace`: the Issues menu no longer offers "Empty sessions"; the show/hide
  control replaces it.

## Impact

- `survey/analytics.py`: the session scope used by the Responses page gains an empty-session
  filter; `compute_session_issues` keeps the same definition through a shared helper.
- Responses views and templates (headline, toggle, table toolbar, Overview, Issues menu) and a per-browser cookie for the toggle.
- `survey/comments.py::session_seq`: response numbers follow the same rule as the table.
- `survey/export.py::excluded_sessions`: adds empty sessions to the exclusion set.
- `survey/views.py` section POST: whitespace stripping for text values.
- In-app changelog (#227): one entry explaining why the headline number dropped.
- No model change, no migration.
