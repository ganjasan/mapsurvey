# Formatted Text questions have no editing interface — creators must hand-write raw HTML

**Type**: feature
**Priority**: medium
**Area**: editor
**Created**: 2026-08-23
**Status**: open

## Description

Picking the "Formatted Text" (`html`) input type in the question modal shows no content
interface at all — just the same Name/Subtext fields as every other type. What actually
happens: the respondent-side template (`survey/templates/html_text.html`) renders the
question's **Subtext verbatim as HTML** (`{{ widget.subtitle | safe }}`). So the creator is
expected to hand-write raw HTML into a plain one-line text input, capped at
`Question.subtext`'s **512 characters**, with no preview of what is legal. Nothing in the
UI explains any of this; the type picker's own hint even promises "headings, bold, links".

## Expected

A WYSIWYG editor for the block's content when `input_type == 'html'` — Quill 2.0.3 is
already loaded on every editor page (`editor_base.html`) and already powers the
thanks-page editor (`thanks_panel.html` → `thanks_html`), so the pattern exists in-repo.

## Notes for implementation

- `subtext` (512 chars) is the wrong home for rich content: a dedicated text field on
  `Question` (migration) or reusing `choices`/JSONB is needed; the thanks-page feature
  already made this exact decision with `SurveyHeader.thanks_html` — mirror it.
- Sanitize on save the way thanks_html does (or does not — check), since the value is
  rendered with `|safe` on the respondent page.
- The modal already switches per-type panels (`toggleTypeScopedFields`) — the Quill
  panel slots into that mechanism; hide Subtext for `html` to remove the trap.
- Migration discipline: worktree PRs collide on migration numbers — check leaves before
  merge.
