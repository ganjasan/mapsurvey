## Why

Reports is meant to be a storytelling module, and after two foundation issues (#703, #692) the
product shows a list of links. The owner set the direction on 2026-11-16: v1 is the **linear
story** — one column, text with charts, maps and quotes between the paragraphs, the shape of the
survey reports made by hand since October — and the acceptance rule is that **every report already
made by hand can be opened by its customer in Reports and edited there as they wish**. The first is
the largest: a neighbourhood-plan report (hero with a strip of key numbers, sections of heading and
text, chart and map pictures with captions, pairs in two columns, quotes with a source line, a
number callout, numbered takeaways, a method note).

Issue #704, first part (epic #712). The second part — live cross-tab and engagement blocks, a map
that may show marks, live numbers in text — follows as its own change.

## What Changes

- **A report is edited on its own**, at `/editor/reports/<uuid>/`, whether or not it has a home
  survey. The survey's Public results tab opens its report's editor. "New report" on the Reports
  list makes a blank one.
- **Block set for a story**: Heading, Text (rich text, sanitised), Image with caption, Key numbers
  (a strip of value + label, typed by hand), Quotes (text + source line, typed or pasted), next to
  the existing Chart, Map, Objects and Budget blocks. A block is full width or half; two halves in a
  row sit side by side.
- **The reader page is a story**: one column, the hero (eyebrow, title, lead), blocks in the flow
  without cards, pairs in two columns, readable on a phone.
- **Numbers typed by hand are allowed** (owner, 2026-11-16).
- **Import and export**: a report leaves as a ZIP (`report.json` + its pictures) and comes back
  from one into any workspace the member may edit; question blocks are re-bound by survey and
  question code when the workspace has them, and dropped with a note when it does not.
- **BREAKING** (editor URLs): the `editor/surveys/<uuid>/public-results/…` write endpoints are
  replaced by `editor/reports/<uuid>/…`; the tab URL stays and redirects.

## Capabilities

### New Capabilities
- `reports-story`: the story block set, the half-width layout, the reader page as a story.
- `reports-editor`: editing a report on its own — create, blocks, settings, publish — and who may.
- `reports-import-export`: the report file, export, import, re-binding of question blocks.

### Modified Capabilities
- `reports`: a survey's tab opens the report's own editor.

## Impact

- `reports/models.py` (+ migration `reports/0003`): block types `heading`, `numbers`, `quotes`;
  `ReportBlock.config`, `ReportBlock.width`.
- `reports/render.py`, `reports/services.py`, `reports/editor_views.py` (keyed by report),
  new `reports/files.py` (export / import), `reports/permissions.py`.
- Templates: `public_results.html` (the story page), `editor/public_results.html` and its
  partials (the editor), `reports/list.html` (New report, Import).
- `survey/urls.py`; comment-thread deep links to a block; `survey/tests/test_reports.py` and two new
  test modules.
- Ops (private repo, not this change): a converter from a hand-made HTML report to the report file.
