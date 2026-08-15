# Design — subtext reaches the respondent

## Decisions

### D1 — Carry subtext on the widget, render it in the section template

The geo types put their subtitle inside their own widget template because the draw button is one
composed control. An ordinary question is a label plus a Django-rendered input, and its subtext
belongs between them — which is the template's business, not the widget's.

So `sublabel` is attached to the widget (the same route `star_icon` and `display_style` already
take), a `question_subtext` filter reads it, and both rendering templates emit one line after the
label. One place per template, no per-type branching.

### D2 — Answerable types only; `image` gets a caption instead

The helper line goes to the eight types that collect an answer. `image` has no label and no
input, so the same line would float without an anchor; it renders as a caption under the picture,
inside the image widget template where the picture is.

`html` already renders its subtext — that field *is* the block's content.

### D3 — The Name stays hidden on `image` and `html`

Both currently drop it, and turning it on is a live change to surveys already published. For
those two types the Name is what the editor's question list shows, so creators use it as an
identifier (`html_block_1`); rendering it would put that on the respondent's screen. Recording
this as intended, rather than fixing it, is the conservative call — and the type picker's
per-type field visibility is the place to act if we later decide the field should not be offered
as respondent-facing copy there.

### D4 — A table test, not eight tests

The bug existed because nothing asserted the mapping. The test builds one question of every
`INPUT_TYPE_CHOICES` entry with a distinct marker, fetches the section over HTTP, and asserts the
full expected table — shown-vs-dropped for name and subtext. A type added later without a
decision fails it.

## Risks / Trade-offs

- **Surveys change appearance on deploy.** Text creators wrote and expected to be visible starts
  being visible. That is the fix, but it is not invisible: some subtext may have been written as
  a note-to-self. Worth a release note; not worth withholding.
- **Long subtext on a scale question** pushes the input down; acceptable, and the same already
  happens on geo questions.

## Migration Plan

None. No schema change; behaviour only.
