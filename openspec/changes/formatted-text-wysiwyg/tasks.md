# Tasks — formatted-text-wysiwyg

## 1. Storage

- [x] 1.1 `Question.subtext` and `QuestionTranslation.subtext`: `CharField(max_length=512)`
      → `TextField(null=True, blank=True)`; migration `0054_formatted_text_body_unbounded`
      (Postgres varchar→text is a metadata-only change, no table rewrite)
- [x] 1.2 `QuestionForm.Meta.widgets['subtext']` keeps the one-line `TextInput` for every
      type; the WYSIWYG replaces it client-side for `html` only
- [x] 1.3 ZIP import stopped truncating `subtext` to 512 (`_import_subtext` in
      `serialization.py`) — the cap would otherwise cut an imported block's body in half

## 2. Sanitization

- [x] 2.1 Allow-list moved out of `views.py` into `survey/html_sanitize.py` as
      `sanitize_creator_html` (forms may not import a view module); `views.sanitize_thanks_html`
      and the `THANKS_*` names stay as aliases so the thanks call sites and tests are unchanged
- [x] 2.2 Sanitize `subtext` on question save when `input_type == 'html'` — base language in
      `QuestionForm.clean()`, translations in `_save_question_translations`, imported ZIPs in
      `serialization._import_subtext`, and the live-preview draft in
      `editor_question_preview_live` so the preview shows what a save would keep

## 3. Editor UI

- [x] 3.1 Question dialog: Quill editor bound to the hidden `subtext` input, shown only when
      `html` is selected; toolbar = header/bold/italic/underline/align/link/list/blockquote/clean
      (no image or video upload — those belong to the Image block)
- [x] 3.2 Quill `text-change` writes into the `subtext` input and dispatches `input`, which is
      the event the live preview already listens for
- [x] 3.3 Stored body loads into Quill when editing an existing block; the one-line input stays
      the value carrier so the form submits unchanged
- [x] 3.4 Per-language Quill instances in the Translations section for `html` blocks
- [x] 3.5 Name relabelled for `image`/`html` ("Editor-only label — respondents don't see it")
      and the Subtext label reads "Content" for `html`
- [x] 3.6 Quill styling for the dialog in `editor_base.html`

## 4. Rich subtext and subheading

- [x] 4.1 `SurveySection.subheading` / `SurveySectionTranslation.subheading` → `TextField`
      (migration `0055`)
- [x] 4.2 `coerce_creator_html` in `html_sanitize.py`: sanitize what carries creator markup,
      escape what doesn't (old rows, old ZIPs, AI drafts)
- [x] 4.3 Data migration `0056` escapes legacy plain-text subtext, skipping `html` blocks and
      anything already rich — so "takes <5 minutes" survives the switch to `|safe`
- [x] 4.4 Every write path coerced: `QuestionForm.clean`, `SurveySectionForm.clean_subheading`,
      question and section translations, ZIP import (the AI path writes through it), live preview
- [x] 4.5 Render as markup: section partial, editor preview frame, geo draw button, image
      caption; `base_survey_template.html` restores the geo subtitle with `.html()`
- [x] 4.6 Compact editors in the question dialog (subtext + per-language) and the section panel
      (subheading + per-language), wired to the existing autosave/preview
- [x] 4.7 `height: auto` on `.ql-editor` — Quill's own `height: 100%` otherwise makes every
      inline editor as tall as the panel

## 5. Tests

- [x] 5.1 A Formatted Text block saves a >512-character body and renders it
- [x] 5.2 `<script>`/`onclick` in a Formatted Text body is stripped on save, base language
      and translation
- [x] 5.3 A creator's "takes <5 minutes" survives on every type (escaped, not swallowed)
- [x] 5.4 The question dialog and section panel markup carry their Quill mounts for `html` (guards against a
      dead editor that every server-side test would otherwise pass)
- [x] 5.5 Section subheading is sanitized on save; formatted subtext reaches the respondent
- [x] 5.6 Full `survey` suite green
- [x] 5.7 Driven in a browser end-to-end: pick Formatted Text → type → save → reopen; body
      stored as `<p>…</p>`, live preview and reload both show it
