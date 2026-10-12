## Context

`SurveyHeader.redirect_url` is a `CharField(max_length=250, default="#")`. `"#"` means "no redirect, show the built-in thanks page". `SurveyHeaderForm.clean_redirect_url` only strips whitespace and maps empty to `"#"`; there is no validation. The value is read raw in four places:

- `survey/views.py` final-section POST: the HTMX branch answers `HX-Redirect: <value>`, the plain branch `HttpResponseRedirect(<value>)`, each with an `== "#"` check for the thanks page.
- `survey/views.py` ~L779 and ~L818: the entry redirect when a survey has no start section.
- `survey/templates/survey_section_block.html`: a "Finish" link with the raw value; the template is not rendered by any view.
- `survey/serialization.py`: export writes it, `import_survey_from_zip` reads it with `_archive_text(…, "#", 250)`.

`survey/content_screening.py` also reads it (phishing signal) and `_rescreen_if_live` runs after a settings save on a live survey; neither changes here.

The settings panel autosaves the whole form (`panel_autosave.js`). A 400 with `{errors: {field: [msg]}}` is already shown next to the field's label, so a validation error is visible; but because the whole form is one POST, an invalid address blocks every other field in that save until it is fixed. The same constraint already applies to `name`.

Production on 2026-10-12: 31 canonical surveys with a broken value, 6 published; the most common shape is `#https://…`.

## Goals / Non-Goals

**Goals:**
- No stored or newly typed value can trap a respondent on the last page or send them to a 404.
- Broken surveys stop failing at deploy time, before and independently of the data migration.
- Creators who meant a link keep it (`#https://…` → `https://…`).
- The settings UI makes "show the thank-you page" the obvious default and explains the link option in plain words.

**Non-Goals:**
- A general "check before publishing" list (separate idea in #271).
- Changing the thanks page itself or `thanks_html`.
- Allow-listing or blocking hosts: phishing stays the job of content screening.
- Relative paths on our own domain: no creator needs one, and `/obrigada` shows they only produce 404s.

## Decisions

**1. One pure normaliser, `survey/redirects.py`.**
`clean_redirect_url(value) -> str` returns `"#"` or a valid absolute http(s) URL, never raises. Steps: strip; drop a leading `#` (repeatedly) when what follows starts with `http://`/`https://` in any case; prepend `https://` to `www.…`; lowercase the scheme; validate with Django's `URLValidator(schemes=['http', 'https'])`; anything that fails → `"#"`. A second function `completion_url(survey) -> str` returns the thanks page URL (`reverse('survey_thanks', args=[str(survey.uuid)])`) or the cleaned value, and every view uses it instead of the `== "#"` checks.
*Why at read time too, not only in the migration:* the deploy order is code then pre-deploy migration on Render, and draft copies and ZIP imports can bring values in through paths we may miss. Reading through the normaliser makes the respondent path correct regardless of what is stored.
*Alternative:* a model `clean()`/`save()` override. Rejected: `save()` overrides surprise `update_fields` callers and `QuerySet.update`, and the readers would still need the thanks-page decision.

**2. The form validates; it does not silently reset.**
`SurveyHeaderForm` gets a non-model `finish_action` field (`thanks` | `link`, radio). `clean()`:
- `thanks` → `redirect_url = "#"`.
- `link` with an empty address → `"#"`, no error (the radio is changed before typing; autosave fires on that change and must not show an error).
- `link` with text → run the same pre-steps as the normaliser (strip `#`, add `https://` to `www.`, lowercase scheme), then validate. Invalid → `ValidationError` on `redirect_url`: "Enter a full web address, for example https://www.facebook.com/yourproject." The stored value is untouched.
`finish_action` initial is `link` when the stored value cleans to a URL, otherwise `thanks`; the address input's initial is the cleaned URL or empty (never `"#"`). A POST without `finish_action` (old clients, tests) is treated as `link` if `redirect_url` is non-empty and not `"#"`, else `thanks`, so existing callers keep working.
*Why refuse instead of normalising to `"#"` in the form:* silently discarding what the creator typed recreates the original problem in reverse (they think the link works).

**3. Template: radio + conditional input, no new JS module.**
Two radios under a "After the last page" label in the Basics card; the address `pr-field` is hidden with a tiny inline toggle (the panel already has inline scripts) when `thanks` is selected. The input gets `placeholder="https://"` and help text "Respondents are sent here after the last page, for example https://www.facebook.com/yourproject." `type="url"` is NOT used: the browser's own validation would block the autosave silently on `www.example.org`, which we accept and fix.

**4. Data migration `0094_normalize_redirect_url`.**
`RunPython` over every `SurveyHeader` (canonical, draft copies, archived versions) with the cleaning logic copied into the migration (migrations must not import app code that may change). Updates only rows whose value changes, with `update_fields=['redirect_url']` via `QuerySet.filter(pk=…).update(…)` to skip signals. Prints `redirect_url normalised: <id> '<old>' -> '<new>'` for each. Reverse is a no-op.

**5. Delete `survey_section_block.html`.** It is unused and is the only place the raw value reached an `href`.

**6. ZIP import** calls `clean_redirect_url` on the archive value. No import-report line: the value was never usable, and the report is for content the creator loses.

## Risks / Trade-offs

- [An invalid address blocks the other settings fields in the same autosave] → The error is shown at the field; the creator fixes or clears it. Same behaviour as an invalid name today. Acceptable.
- [`URLValidator` rejects something real, e.g. an IDN or a very long query] → Max length stays 250; Django's validator accepts IDNs. A rejected value shows the error, nothing is lost.
- [The migration changes creators' data] → It only turns values that never worked into the thank-you page, or recovers the link they meant. The ids are printed in the deploy log; the four affected live creators get an email.
- [Content screening sees fewer raw values] → Valid http(s) URLs are what it scores; junk text never contained a host.
- [Draft copy published over the canonical survey carries an old value] → Draft copies are migrated too, and readers normalise anyway.

## Migration Plan

1. Merge → Render deploy runs `migrate` in pre-deploy: `0094` normalises the rows and logs changes.
2. Check the deploy log for the list of changed ids and confirm the published ones (334, 193, 584, 161, 257) are among them, plus that `34` (`Test1`) became `"#"`.
3. Send the creator emails (ops repo).
Rollback: revert the PR. The migration's reverse is a no-op; the normalised values are valid under the old code as well.

## Open Questions

None.
