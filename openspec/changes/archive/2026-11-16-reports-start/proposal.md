## Why

"Show me something already — I'd rather fix than build." After a survey closes with 146 responses
a blank report is where the hand-made kit begins today. Issue #705 (epic #712).

## What Changes

- **A start page**, `/editor/reports/start/`: cards that each do their action on one click — a
  draft from a survey in one of four arrangements, a blank report, a copy of an earlier report.
- **The draft is built by rules**, not by a model (`reports/drafting.py`): who took part first,
  then one fitting block for every question people answered, in the survey's order with its
  sections as headings; free-text questions arrive as quotes to pick from, hidden until picked;
  text the author must write arrives as hidden blocks holding a prompt.
- **Four arrangements**: Consultation summary, Council paper (numbered sections, results as
  tables), Engagement update (short, live, a link to take part), You said — we did.
- **A copy** is the report file's round trip in memory, unpublished and workspace-only.
- **"Create report" where the data is**: the Reports list, the Responses page of a published
  survey, the survey's responses dataset in Data.
- Events `report_entry_seen` (surface) and `report_created` (surface, start, template).
- `Report.template` records the arrangement a draft was made with.

## Capabilities

### New Capabilities
- `reports-start`: the start page, the rule-built draft and its arrangements, the copy, the entry
  points.

### Modified Capabilities

None.

## Impact

- New `reports/drafting.py`, `reports/templates/reports/start.html`; `reports/views.py`
  (`report_start`), `reports/models.py` (+ `reports/0005`), `survey/urls.py`,
  `survey/product_events.py`.
- `reports/list.html` ("New report" opens the start page), `analytics_dashboard_v2.html` and
  `data/dataset.html` (entry links).
- Not here: a banner when a survey closes (the entry sits on Responses for every published
  survey), hotspot naming ("the places with most marks" are the map block itself), the PDF look of
  the Council paper (#707).
