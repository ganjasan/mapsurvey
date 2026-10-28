# Mandatory Thanks page with a rich-text editor and required branding

## Why

The "thank you" page a respondent sees after submitting is currently edited as a
raw multilingual JSON blob (`thanks_html`) buried in Survey settings — creators
have to hand-write HTML keyed by language code. It reads as a developer field,
not a page you design (user, 2026-07-06). It should be a first-class part of the
survey: a real page every survey has, edited with a normal WYSIWYG editor, sitting
as the last step in the Build flow.

Separately, the "Made with Mapsurvey" acquisition loop (from the merged
`made-with-mapsurvey-viral-loop` work) is currently opt-out via `show_branding`.
For the free tier it should be **mandatory** — always shown — while keeping the
flag in the data model so a future paid tier can turn it off.

## What Changes

- **Thanks page is a Build step, not a settings field.** A pinned **"Thanks page"**
  entry sits at the *bottom* of the Build sections sidebar (mirroring the pinned
  "Survey settings" at the top). Selecting it swaps a dedicated editor into the
  center panel. The raw `thanks_html` textarea is removed from Survey settings.
- **Rich-text (WYSIWYG) editor.** Per survey language, the creator edits the
  thank-you content visually (headings, bold/italic, links, lists) instead of
  typing HTML. Content is stored in the existing `thanks_html` JSONField (a
  per-language dict of HTML) — no new content field, existing data still renders.
- **Server-side HTML sanitization.** The WYSIWYG output is sanitized against a
  tag/attribute allow-list before storage/render (it is shown `|safe` to public
  respondents), closing the stored-XSS surface the raw field left open.
- **Mandatory "Made with Mapsurvey".** The branding link renders unconditionally
  on the survey, thanks, and results pages. `show_branding` stays on the model as
  a *future* paid-tier preference but is no longer a creator-facing toggle (which
  also fixes a latent autosave bug where the un-rendered checkbox was posting
  `False`). The Thanks editor shows the branding as a fixed, non-editable footer
  so creators see exactly what respondents get.
- **The Thanks page always exists.** Empty content falls back to a default
  "Thank you!" message; the page always carries the share action and the branding.

## Impact

- Affected specs: `survey-thanks-page` (MODIFIED), `viral-loop-branding` (MODIFIED)
- Affected code: `survey/models.py` (helpers; `show_branding` stays, drops from
  form), `survey/editor_forms.py` (remove `show_branding`/`thanks_html` from the
  settings form), `survey/editor_views.py` (+ thanks-panel view, sanitize on
  save), `survey/urls.py` (+ thanks-panel URL), `survey/views.py` (thanks render),
  templates (new `thanks_panel.html`, sidebar pinned entry, settings panel drops
  the Thanks card, `_made_with_mapsurvey.html` renders unconditionally),
  `requirements.txt` (+ `nh3` sanitizer). No content migration (reuses
  `thanks_html`); no schema change beyond keeping `show_branding`.
