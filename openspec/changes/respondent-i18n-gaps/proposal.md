## Why

A customer running a Polish survey reported that the "Other" write-in field says "Please specify"
in English (GitHub #285). An audit found the cause is systemic: every respondent-facing feature
shipped after the creator-UI localization (late Aug 2026) — the "Other" option, spray tool,
Objects-on-the-map, thumbs, the abuse footer — reached the templates but never the catalogs, and
nothing fails when that happens. Some strings were never marked for translation at all, and several
respondent pages ignore the survey's language entirely. A respondent should not meet English chrome
in a survey its creator published in another language.

## What Changes

- **Fill the catalogs.** Every respondent-facing msgid gets a real (non-fuzzy) translation in every
  survey locale the editor offers (74 non-English catalogs). This includes the 36 msgids that exist
  in templates but no catalog, and the four catalogs (`ar`, `fa`, `he`, `ur`) that are empty today,
  so surveys in those languages show the whole interface in English.
- **Mark hard-coded English for translation** on respondent surfaces: thanks-page share button,
  map control titles (zoom, locate, layers), basemap names, ranking hint and screen-reader
  announcements, dropdown search placeholder, file-upload errors, the password-gate error, the
  abuse-report reasons, and captions on public results.
- **Render every respondent page in the survey's language**: thanks, password gate, closed and
  unavailable pages, the abuse report pages and the upload endpoint, not only the section pages.
- **Guard test**: the suite fails when a respondent-facing msgid has no translation in a survey
  locale, so the next feature cannot ship English chrome silently.

Out of scope: creator/editor and billing strings (~460 msgids, separate change), marketing landing
pages, default legend labels of styled layers (`Other`, `Class n` — saved into the
layer style as editable creator text, so they are content, not chrome), right-to-left page layout for `ar`/`fa`/`he`/`ur` (strings only).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ui-internationalization`: respondent-facing strings must be translated in every survey locale,
  with a guard test; Leaflet controls and client-side messages are covered.
- `survey-language-selection`: the selected survey language applies to every respondent page, not
  only the sections.

## Impact

- `survey/locale/*/LC_MESSAGES/django.po` and `.mo` (74 locales).
- Templates: `survey_thanks.html`, `base_survey_template.html`, `partials/basemap_layers.html`,
  `choice_dropdown.html`, `ranking.html`, `file_upload.html`, `public_results.html`.
- JS: `survey/assets/js/components/ranking.js`, `survey/assets/js/file_upload.js`.
- Python: `survey/views.py` (language activation, password error), `survey/content_screening.py`
  (`REPORT_REASONS`), `survey/templatetags/i18n_extras.py`.
- `survey/tests.py`: new catalog-completeness guard and language-activation tests.
