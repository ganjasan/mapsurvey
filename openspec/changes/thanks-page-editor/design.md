# Design — Thanks page editor

## Context

`SurveyHeader.thanks_html` is a `JSONField` holding either a plain HTML string or
a `{lang: html}` dict; `resolve_thanks_html(thanks_html, lang)` picks the
language (lang → en → first). The public `survey_thanks` view renders it `|safe`,
then a share button, then `_made_with_mapsurvey.html` (gated on `show_branding`).
The Build editor already has the pinned-panel pattern: `editor_survey_settings_panel`
+ URL `settings-panel/` + `?panel=settings`, swapped into `#section-content` via
HTMX, with a matching `.sidebar-pinned` entry.

## Goals / Non-Goals

- **Goal:** a WYSIWYG thanks editor reachable as the last Build step; mandatory,
  always-present thanks page; mandatory branding with a retained future-paid flag.
- **Non-Goal:** turning the thanks page into a general page builder (blocks,
  images galleries). One rich-text body per language + the fixed share/branding
  footer is enough. No paid-tier gating logic yet (only the flag is preserved).

## Decisions

### D1 — Reuse `thanks_html` as the store (no new field, no migration)
WYSIWYG output is HTML; `thanks_html` already stores per-language HTML. The editor
reads/writes `thanks_html[lang]`. Existing surveys render unchanged. Rationale:
smallest change, backward compatible, `resolve_thanks_html` already handles it.

### D2 — Editor: Quill (CDN), one instance per language tab
Use Quill 2.x from CDN (the app already loads Bootstrap/Leaflet/HTMX from CDNs).
A language switcher (only when the survey has >1 language) swaps which
`thanks_html[lang]` the editor binds to. Toolbar: headings, bold/italic,
link, ordered/bullet list, clean. On change → debounced autosave (same pattern
as the settings panel: POST HTML, get JSON back). Rationale: a mature,
familiar "normal editor"; produces clean HTML we can sanitize; no build step.
Alternative considered: a hand-rolled `contenteditable` + `execCommand` toolbar —
rejected (execCommand deprecated, more edge cases, worse UX for a headline feature).

### D3 — Sanitize on save with `nh3` (allow-list)
Quill output is still attacker-influenced (paste, or a malicious creator toward
their own respondents — the current raw field is unsanitized `|safe`). Sanitize
server-side in the thanks-panel save view with `nh3.clean(html, tags=…, attributes=…)`
before persisting: allow `h1-h4,p,br,strong,em,u,a,ul,ol,li,blockquote,span`;
`a`→`href,title,target,rel` (force `rel=noopener`), strip everything else.
`nh3` (Rust `ammonia` binding) is fast and maintained. Store sanitized HTML so
render stays a simple `|safe`. Rationale: defense-in-depth; removes the existing
XSS surface rather than carrying it forward.

### D4 — Placement: pinned "Thanks page" at the bottom of the sidebar
Add a second `.sidebar-pinned` block *after* `section-list` / "New Section"
(the top pinned block keeps "Survey settings"). New view
`editor_survey_thanks_panel` + URL `thanks-panel/` + `?panel=thanks`; the
`editor_survey_detail` view accepts `panel=thanks` to load it initially; the
sidebar JS click handler mirrors the settings-panel swap. The panel reuses the
shared `.pr-ctxbar/.pr-card/.pr-field` vocabulary. Rationale: "last step" is
literally the last sidebar entry; reuses a proven pattern; no new nav concepts.

### D5 — Mandatory branding, flag retained
`_made_with_mapsurvey.html` renders unconditionally (drop the `{% if
survey.show_branding %}` guard). Keep the `show_branding` model field (default
True) as a forward-looking paid-tier preference; remove it from
`SurveyHeaderForm` so it is not creator-editable (this also fixes the latent
autosave bug: the settings panel renders explicit fields and never emitted
`show_branding`, so each autosave was posting it as unchecked→`False`). The
thanks editor renders the branding block read-only in its live preview.
Rationale: honors "mandatory everywhere, but keep a flag for future paid users."

### D6 — Editor layout & preview
The thanks panel: a `.pr-ctxbar` ("Thanks page / The last screen respondents
see"), a Quill editor card (with the language tabs), and a live preview card that
renders the current HTML + the fixed share button placeholder + the mandatory
branding footer, so WYSIWYG ≈ what respondents see. Autosave status like the
other panels.

## Risks / Trade-offs

- **New dependency (`nh3`, Quill CDN).** `nh3` is a small wheel; Quill is a
  well-known CDN asset. Both are low-risk; sanitize is the security-relevant one.
- **Sanitization could strip creator HTML** that pre-existed in `thanks_html`
  (raw). Mitigation: the allow-list covers ordinary formatting; sanitize only on
  *save* (existing stored HTML renders as-is until re-saved) — no destructive
  migration. Log/verify nothing common is stripped.
- **`show_branding` leaving the form** must not break existing tests that post the
  settings form or assert the toggle — audit and update.

## Migration Plan

No data migration. `thanks_html` values keep working. `show_branding` column
stays. First save through the new editor sanitizes that survey's HTML.

## Open Questions

- Quill theme (snow) styling vs. the app's look — minor CSS reconciliation.
- Should the language tabs also drive a per-language preview of the branding
  string? (Branding is already `{% trans %}`-localized; low priority.)
