## Context

`Report.survey` is nullable and documented as "home survey, not an owner of its data"; blocks name
`dataset` + `question_code`, and `services.add_question_block / add_view_block / add_compare_block`
already accept any survey of the workspace. Only the editor view and the library restricted data
blocks to `request.survey`. #737 (the same day) made "New report" a one-click blank report and
reduced the start page to the blank card, so the choice of a survey must not come back as a step
before the editor.

## Goals / Non-Goals

**Goals:** a blank report can show data in the same number of clicks as a survey's own report;
one report can read several surveys; the home survey can be set, changed and cleared.

**Non-Goals:** bringing the arrangements back to the start page; a cross-tab across two surveys;
changing the API / MCP (they already take a survey).

## Decisions

- **The library is where the survey is chosen.** A `source` select at the top of the library; its
  change fetches the data groups (`library` route, a fragment) and swaps them in place. `source`
  is posted with the tile, and `_block_add` resolves it among the surveys the member sees. With
  no `source` the view behaves exactly as before (`request.survey`), so the survey tab is
  untouched.
- **Adoption happens in the editor view, not in the services.** The first data block's survey
  becomes the home survey only on this surface; API and MCP callers name a survey explicitly and
  keep their behaviour.
- **Adoption and the settings card need the editor role on the survey.** A report with a home
  survey is editable only with that role (`may_edit_report`), so adopting a survey the author
  merely sees would lock them out of their own report. The block is still added.
- **The home survey is a plain form, not autosave.** It changes the hero, the library, the tabs
  and the publish rule; the page reloads.
- **Surveys offered:** canonical, not deleted, not draft, visible to the member — the list
  `report_start` always used.
- **A started report is never auto-drafted.** `scaffold_report` fills the survey's oldest report
  when it is empty; an adopted blank report could be that one. It now skips a report with
  `created_by` set (lazy tab reports have none).
- **Hidden switches keep their values** through hidden fields, because the settings form treats a
  missing checkbox as "off".

## Risks / Trade-offs

- A report whose home survey is cleared while it is the survey's tab report: the tab opens the
  next report or starts an empty one — the same outcome as deleting it, which the delete dialog
  already explains.
- The library fragment is one more request per survey switch; it draws the same tiles the page
  would.
