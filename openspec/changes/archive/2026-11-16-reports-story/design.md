## Context

After #703 a report is a workspace object, but it is edited only through its home survey's Public
results tab and its page is a dashboard of cards. Reports made by hand since October are HTML
documents: a hero with key numbers, headed sections of text, chart and map pictures with captions,
quotes, a numbered list of takeaways. The owner's acceptance rule (2026-11-16): each of them opens
in Reports and can be edited by its customer.

## Goals / Non-Goals

**Goals:** the linear story as the reader page; the blocks a hand-made report is made of; an editor
that works for a report without a survey; a report file to export and import; the first hand-made
report imported and looking like itself.

**Non-Goals:** live cross-tab and engagement blocks, a map that may show marks, live numbers inside
text (next change of #704); the map-led story; PDF, embeds, templates, the Pro gate (#705–#709).

## Decisions

1. **One editor, two ways in.** The views are written once and exported twice, `on_survey(view)`
   and `on_report(view)`; both set `request.report` / `request.survey`, and `_urls(request)` hands
   the page every URL it needs, so templates name no route. Alternative — moving everything to the
   report's address and redirecting the tab — would have rewritten some forty tests of the tab for
   no gain to the user.
2. **Story blocks are rows of the same table.** `heading`, `numbers`, `quotes` join `text` and
   `image` in `ReportBlock.block_type`; what they hold beyond text lives in `ReportBlock.config`
   (`{"items": […]}`), cleaned by `reports.story.clean_config` on every way in (editor, import).
   A table per block type was rejected: a story is an ordered list, and one `order` over one table
   is what makes reorder, export and import trivial.
3. **Half width, not a layout block.** `ReportBlock.width` is `full | half`; the renderer pairs two
   consecutive halves (`render.story_rows`). A "columns" container block would nest blocks and
   complicate the outline, reorder and the file format for one use.
4. **Typed numbers and quotes** (owner, 2026-11-16). The editor takes them as lines,
   `value | label` and `quote | source`: one textarea autosaves like every other field, and pasting
   a list from a document works. Live numbers bound to a view come with the live blocks.
5. **Text is rich and sanitised.** `reports.story.clean_html` is `coerce_creator_html`: the same
   allow-list as every creator-written field. The payload carries `html`; a snapshot frozen before
   this change has only `body` and the template escapes it — no snapshot version bump, no stale
   pages.
6. **The file is a ZIP with `report.json`.** Question blocks are recorded by survey uuid and
   question code and re-bound on import through `data.questions.question_of`; a block that cannot
   be bound is left out and named. An import is never published and is workspace-only: a hand-made
   report says "not for publication without the association's agreement".
7. **The converter of hand-made HTML lives in the ops repo** (`scripts/report_html_to_file.py`):
   it reads customers' reports, which never enter the public repo. The product only knows the
   report file.
8. **A report without a survey shows no comment threads**: threads hang on a survey
   (`CommentThread.survey` is required). Comments on such reports come with Review (#706).

## Risks / Trade-offs

- [Half-width pairs depend on order] → the outline marks a half-width block with "½"; a lone half
  simply takes the row.
- [A text block's Quill sits inside an autosaving form] → the hidden field fires `input`/`change`
  on user edits only, so loading the editor does not save.
- [Imported pictures are stored on the public media tier like every report image] → the report
  itself is unpublished; an unguessable file name is the same protection uploaded block images
  have today. Private media for unpublished reports is noted for #709.

## Migration Plan

`reports/0003`: add `config` and `width`, widen the `block_type` choices. No data change. Rollback:
revert; the columns are unused by older code.
