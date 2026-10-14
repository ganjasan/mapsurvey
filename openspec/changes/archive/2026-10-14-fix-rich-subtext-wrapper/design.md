## Context

`Question.subtext` (and the image caption, which is the same field) is sanitized creator HTML
whose top-level nodes are `<p>`, lists and headings. Templates that predate the rich-text editor
wrap it in `<p class="…">`. The HTML parser auto-closes an open `<p>` when it meets a block
element, so the styled wrapper ends up empty and the content becomes an unstyled sibling.

## Goals / Non-Goals

**Goals:** the hint renders once, inside its styled wrapper, on the respondent page, the editor
preview and the draw button.

**Non-Goals:** sub-question popups (`SurveySectionAnswerForm.as_p()`) do not render subtext at
all today; that is a separate decision, not this bug.

## Decisions

- `<div>` instead of `<p>` for every wrapper of creator rich text. The CSS selectors are
  class-only (`.geo-question-subtitle`, `.question-card__subtext`, `.image-block__caption`), so
  the styling is unchanged. The geo-button JS finds the wrapper by class too.
- Zero the margins of the first and last child inside the wrapper rather than of every `<p>`,
  so multi-paragraph hints keep their spacing between paragraphs.
- The guard test works on the markup, not a parsed tree: Python's test client does not
  auto-close `<p>` the way a browser does, and no HTML5 parser is in the lock file. For every
  input type it gives the question a `<p>…</p>` hint, renders the section, and asserts the hint
  appears once and that no `<p>` is open before it. On the old templates it fails for all 18
  types that show a hint.

## Risks / Trade-offs

- A `<div>` inside a `<button>` (draw button) is phrasing-content-invalid in strict HTML, but the
  button already contains `<div>`s and every browser lays it out; the existing `<p>` was equally
  invalid there.
