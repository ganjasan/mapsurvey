## 1. Normaliser

- [x] 1.1 Create `survey/redirects.py` with `clean_redirect_url(value) -> str` (strip, drop leading `#` before http(s), `www.` → `https://`, lowercase scheme, `URLValidator(schemes=['http','https'])`, else `"#"`; never raises) and `completion_url(survey) -> str` (thanks page URL or the cleaned link)
- [x] 1.2 Unit tests (GIVEN/WHEN/THEN) for `clean_redirect_url`: `#`, empty, `None`, `#tag`, `#https://x.org/a`, `##https://x.org`, `Https://x.org`, `www.x.org/a`, `/obrigada`, `-`, free text, valid https URL unchanged

## 2. Respondent redirects

- [x] 2.1 Replace the `== "#"` branches in the final-section POST (HTMX `HX-Redirect` and plain redirect) with `completion_url(survey)`
- [x] 2.2 Replace the raw `survey.redirect_url` in the no-start-section entry redirects (~L779, ~L818) with `completion_url(survey)`
- [x] 2.3 Delete the unused `survey/templates/survey_section_block.html`
- [x] 2.4 Tests: last-section submit with `#projectname` (plain POST) and `#https://example.com` (HTMX) lands on the thanks page; `/obrigada` and `-` land on the thanks page; `https://example.com` still redirects there

## 3. Settings form and panel

- [x] 3.1 `SurveyHeaderForm`: add `finish_action` radio (`thanks` | `link`) with initial derived from the stored value; address initial = cleaned URL or empty; `clean()` per design decision 2 (including the POST-without-`finish_action` fallback); error text with an example address
- [x] 3.2 `survey_settings_panel.html`: "After the last page" radios, address field shown only for "Open a web address", `placeholder="https://"`, help text with an example; inline toggle that does not break the shadowed-by-draft disabling
- [x] 3.3 Tests: default survey renders the thank-you option with an empty hidden address; a survey with a link renders the address option; valid save; `#https://…` and `www.…` are fixed on save; `#projectname`, `/thanks`, free text → 400 with a `redirect_url` error and value unchanged; switch to thank-you → `"#"`; link with empty address → `"#"`, no error; POST without `finish_action` keeps working
- [x] 3.4 Check in a browser (dev server on offset 570): toggle, autosave status, the 400 error shown at the field, Russian UI strings

## 4. Import and data migration

- [x] 4.1 `import_survey_from_zip`: pass the archive value through `clean_redirect_url`; test with `"#thanks"` → `"#"` and `"#https://x.org"` → `"https://x.org"`
- [x] 4.2 Migration `0094_normalize_redirect_url` (RunPython, cleaning logic copied in, reverse no-op, prints each changed id); confirm no newer migration landed on `origin/master` first
- [x] 4.3 Migration test: run the forward function over rows with `#https://…`, `Https://…`, `#tag`, `/obrigada`, `-`, `Wat is je naam`, `#`, `https://ok.org` and assert the mapping

## 5. Copy, changelog, docs

- [x] 5.1 Translations: add the new strings to the ten creator-UI catalogs (de fr es pt pl id nl it et fi; `ru` too, for completeness) and compile; verify with `gettext` and the language cookie
- [x] 5.2 Changelog entry `survey/changelog/<release-date>-finish-link.html` (`kind: fixed`, link `editor`): what changed and why, two short paragraphs
- [x] 5.3 Update the CLAUDE.md note if any (redirect rule: read through `survey/redirects.py`, never raw)

## 6. Verify and ship

- [x] 6.1 Run `./run_tests.sh survey` once after the changes; summarise the delta against the baseline
- [x] 6.2 Open the PR referencing #271 (no `[render preview]` unless asked)
- [x] 6.3 After deploy: check the pre-deploy log for the normalised ids and that the published surveys are among them
- [x] 6.4 Draft the four creator emails in the ops repo (short "thanks, fixed" style, `#https://` cases: the link now opens; others: respondents now see the thank-you page and how to add a link); send only after the owner's go-ahead — Jessica sent 2026-10-12; IBMF left to the owner to send by hand in their thread; the two ITS student surveys and the earlier-contacted creator get no extra letter (owner decision)
