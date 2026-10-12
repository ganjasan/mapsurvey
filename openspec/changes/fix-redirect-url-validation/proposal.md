## Why

`SurveyHeader.redirect_url` is a free-text field that nothing validates, and whatever a creator types there becomes the redirect after the last section. On 2026-10-12, 31 surveys held something other than `#` or an http(s) URL, and 6 of them were published. On those surveys respondents press Finish and stay on the last page (`#hashtag`, `#https://…`), or land on a 404 (`-`, `/obrigada`). The worst published case had 61 respondents press Finish 328 times; one creator concluded it was a software bug and told her respondents so. Issue #271.

The values explain the cause. The input is pre-filled with the stored default `#`, so creators type the URL after it (`#https://www.facebook.com/…`, the most common pattern). The label "Redirect URL" means nothing to a non-technical creator, so some write a thank-you message or a hashtag there.

## What Changes

- Survey settings replaces the bare "Redirect URL" input with a choice: **After the last page** — "Show the thank-you page" (default) or "Open a web address". The address input appears only for the second option, starts empty (never pre-filled with `#`), and carries a plain-language example.
- Saving validates the address: only an absolute `http://` / `https://` URL is accepted. A pasted `#https://…` loses the `#`, a bare `www.…` gains `https://`, and the scheme is lowercased. Anything else is refused with a field error that names the field and shows an example. "Open a web address" with an empty box saves as the thank-you page.
- One normaliser decides where a respondent goes after the last section. Every reader uses it: both final-section redirect paths, the no-start-section entry redirects, and ZIP import (which is also the AI-generation path). A stored value that is not a valid http(s) URL means "show the thank-you page", so surveys that are broken today stop trapping respondents as soon as this deploys.
- A data migration rewrites the stored values: `#http(s)://…` → the URL without `#`, `Https://` → `https://`, everything else invalid → `#`. It prints the ids it changed.
- The unused `survey_section_block.html` template (its "Finish" link put the raw value into `href`) is deleted.
- A `kind: fixed` changelog entry.
- Outside the code: after the deploy, a short email to the creators of the four affected published surveys not yet contacted (prepared in the private ops repo).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `survey-thanks-page`: "Custom redirect URL takes precedence" now applies only to a valid absolute http(s) URL; any other stored value sends the respondent to the thanks page. ZIP import normalises the value.
- `survey-editor`: "Survey settings editing" gains the after-the-last-page choice and the address validation.

`survey-content-screening` keeps its behaviour (it still reads `redirect_url` and re-screens on save of a live survey). No delta.

## Impact

- `survey/editor_forms.py` (`SurveyHeaderForm`: choice field, `clean_redirect_url` / `clean`), `survey/templates/editor/partials/survey_settings_panel.html` (and the full-page settings form if it renders the field).
- New helper module for the normaliser (pure function, no DB), used by `survey/views.py` (final-section POST: HTMX `HX-Redirect` and plain redirect; entry redirects ~L779 / ~L818) and `survey/serialization.py` (`import_survey_from_zip`).
- New migration `0094_normalize_redirect_url` (data only, reversible as a no-op).
- `survey/templates/survey_section_block.html` removed.
- `survey/changelog/2026-10-xx-finish-link.html`.
- Tests in `survey/tests.py`.
- The autosave panel already shows a 400's field error next to the field label (`panel_autosave.js`); no change there.
