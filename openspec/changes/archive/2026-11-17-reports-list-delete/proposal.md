## Why

A report can be deleted only through a link in the builder's settings panel, and that link is shown
only for a report without a home survey. A report made from a survey — a draft, a copy for the next
round, a test — cannot be deleted from the interface at all, and the Reports list offers no Delete
action for any report (#733, follow-up to #731).

## What Changes

- The Reports list shows a Delete action on every row the member may edit. It opens the existing
  page that says what goes with the report; nothing is deleted by the click itself.
- The builder's report settings show "Delete report…" for every report the member may edit, with or
  without a home survey.
- The delete page says when the report is the one its survey's Public results tab opens: after the
  deletion that tab opens the survey's next report, or starts an empty one.

- The builder's outline and context panel are resized by dragging their inner edge (double click =
  default); the widths are kept per browser. The builder script is shared, so the Sites builder
  gets the same handles.
- On the report start page the busy spinner of a pressed card turns in place: the card's icon was
  stretched to the card's width, so the spinning glyph circled around the card.

## Capabilities

### Modified Capabilities

- `reports-editor`: the requirement "A report can be deleted" names where the action is offered and
  covers a report with a home survey.

## Impact

- `reports/views.py` (`report_list`, `report_delete`), `reports/templates/reports/list.html`,
  `reports/templates/reports/delete.html`, `reports/templates/reports/editor/_page_panel.html`, `reports/templates/reports/start.html`.
- `survey/assets/js/site_builder.js`, `survey/assets/css/site_builder.css` (`initPanelResize`, `--lb-rail-w`, `--lb-panel-w`,
  `localStorage['msBuilderPanels']`).
- One new creator string in the ten catalogs.
- No model, API or MCP change: `services.delete_report` is unchanged.
