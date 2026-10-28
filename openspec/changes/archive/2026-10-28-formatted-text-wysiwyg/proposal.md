# A real editor for the Formatted Text block

## Why

The "Formatted Text" block (`input_type='html'`) is the only way a creator can put
their own words on a survey page — an intro, an instruction, a consent note. Its
content lives in `Question.subtext`, and the question dialog renders `subtext` as a
**single-line `<input type="text">`** capped at 512 characters (`CharField(max_length=512)`).

Selecting the block therefore shows the creator no place to write: the only field on
screen is a one-line box shared with every other question type, whose label ("Subtext")
does not say it is the block's body, and which cannot hold a paragraph, a line break or
a heading. To get anything formatted out of it a creator would have to hand-type HTML
into that one line. In practice the block is unusable and creators cannot add their own
text at all (user, 2026-08-23).

The survey already has a working rich-text editor for exactly this job — the Thanks page
(Quill 2.0.3, loaded in `editor_base.html`, sanitized server-side with `nh3` via
`sanitize_thanks_html`). The Formatted Text block should use the same one.

## What Changes

- **A WYSIWYG editor in the question dialog.** When `Formatted Text` is the selected type,
  the Subtext input is replaced by a Quill editor labelled as the block's content, with the
  same toolbar the Thanks page offers minus the uploads (headings, bold/italic/underline,
  alignment, link, lists, blockquote, clean). Every other input type keeps the plain
  one-line Subtext field it has today.
- **Content is no longer capped at 512 characters.** `Question.subtext` and
  `QuestionTranslation.subtext` become `TextField`. Existing content is untouched — the
  block keeps storing its body in `subtext`, so published surveys, serialization,
  versioning and translations all keep working with no data migration.
- **Server-side sanitization.** `html` blocks are rendered `|safe` to respondents
  (`html_text.html`), so their `subtext` is sanitized on save against the same allow-list
  the Thanks page uses, closing a stored-XSS hole that predates this change. The sanitizer
  is renamed to `sanitize_creator_html` with `sanitize_thanks_html` kept as an alias.
- **The Name field is labelled for what it is.** For `image` and `html` the name is never
  shown to respondents (existing `question-subtext` spec); the dialog now says so instead
  of presenting "Name" as if it were a heading.
- **Translations get the same editor.** In a multilingual survey each language's Formatted
  Text body is edited with its own Quill instance in the Translations section, not a
  one-line input.
- **Question subtext and section subheading become rich text too.** They are the other two
  places a creator writes prose, and both had the same problem in a smaller form: a one-line
  input, and HTML to be hand-typed if you wanted a link. Both are now authored in a compact
  editor (emphasis, links, lists; alignment for the subheading) and rendered as markup —
  which the subheading *already* was, `|safe` and unsanitized, so this closes that hole while
  opening the feature.
- **Old plain text keeps working.** These fields hold two kinds of value now: rich text from
  an editor, and plain text from everything that predates one (existing rows, older ZIP
  exports, AI-generated drafts). `coerce_creator_html` sanitizes the first and *escapes* the
  second, and a data migration escapes the rows already in the database — otherwise a
  creator's "takes <5 minutes" would silently lose its "<5 minutes" the day the template
  stopped escaping.

## Impact

- Affected specs: `formatted-text-block` (ADDED)
- Affected code: `survey/models.py` (`subtext` and `subheading` → `TextField`) + migrations
  `0054`–`0056` (the last one escapes legacy plain text), `survey/html_sanitize.py` (new home
  of the allow-list, plus `coerce_creator_html`), `survey/views.py` (keeps the thanks-era
  names as aliases), `survey/editor_forms.py` (sanitize on save for question and section),
  `survey/editor_views.py` (translations, live preview), `survey/serialization.py` (ZIP
  import — which is also the AI generation path), templates: the question dialog and section
  panel gain editors; `survey_section_partial.html`, `question_preview_frame.html`,
  `leaflet_draw_button.html`, `show_image.html` render subtext as markup, and
  `base_survey_template.html` restores a geo subtitle with `.html()` rather than `.text()`.
- Respondents see existing content unchanged — that is what migration `0056` is for.
