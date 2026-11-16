## Context

`services.set_published` flips `is_published`; the editor's "Publish page" button posts it
directly. A report may now hold quotes typed or drafted from free-text answers and a map of marks.
Comment threads on blocks exist for a survey's report (anchor kind `block`, the shared drawer).

## Decisions

1. **One function, `reports.checks.run(report)`**, returns two lists — `privacy` and `other` — of
   plain items (key, message, block, fix). The dialog renders it; `set_published` asks it one
   question, `needs_ack`. A check is a few lines there, never a branch in a view or a template.
2. **What holds a publication back is narrow**: a visible quote or a map of marks, until the
   author ticks one box. The owner ruled (2026-11-16) that showing them is the survey owner's
   call; the product's part is that the call was made knowingly. A threshold of 1 is listed but
   does not block: published pages with K = 1 exist today and must keep republishing.
3. **"Renders nothing" is asked of the renderer** (`ReportService._build_block(block) is None`),
   not re-derived: the check can never disagree with the page.
4. **The dialog body is fetched each time it opens** (HTMX into the modal), so it reflects the
   report as saved by autosave; deleting an empty block from the list reloads the body.
5. **Audience and live/frozen ride on the same POST** (`visibility`, `mode`); the settings page
   keeps its own controls.
6. **A map's description lives in `block.content`**, the field captions already use: shown under
   the map, and `role="img"` + `aria-label` on the map container.
7. **Preview widths resize the existing pane** (420 px, or 55 % of the window): one iframe, no
   second preview route. The PDF preview arrives with the PDF (#707).
8. **Comments**: blocks of a survey's report already carry threads (badge in the outline, drawer,
   mail). A report without a home survey has none, because a thread belongs to a survey; lifting
   that means a second anchor owner in `CommentThread` and is left for a follow-up.

## Risks / Trade-offs

- [A script that publishes a report with quotes now gets 400 `ack_required`] → only reports made
  in this epic can have quotes or marks; nothing on master does.
- [The confirmation is a checkbox, easily ticked] → it is a record of a decision, not a gate; the
  quotes are written out right above it.

## Migration Plan

No schema change. Rollback: revert.
