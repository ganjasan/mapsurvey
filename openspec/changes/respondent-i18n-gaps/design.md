## Context

Respondent chrome was localized in 2026-08 (backlog #7): 31 msgids, filled in ~70 of the 75 catalogs
under `survey/locale/`. The creator UI followed (`creator-ui-localization`), filling 10 catalogs.
Since then features have added `{% trans %}` tags without catalog entries, and a few were written
with no i18n at all. Nothing in the suite compares template msgids with the catalogs, so the gap is
invisible until a customer sees English in their survey.

Constraints inherited from `creator-ui-localization`:

- `makemessages` merges by msgid but also writes `#, fuzzy` guesses by string similarity. A fuzzy
  entry is ignored by `compilemessages` today and lies the day someone drops the flag.
- `TranslationCatalogHygieneTest` rejects one msgstr reused across non-synonymous msgids.
- `.mo` files are committed; production does not compile catalogs at build time.

Language activation: `LocaleMiddleware` resolves from cookie / Accept-Language. Only
`survey_language_select` and `survey_section` call `translation.activate()` with the survey
language, from `request.session['survey_language']`.

## Goals / Non-Goals

**Goals:**

- No English chrome on any respondent page of a survey in any offered language.
- A test that turns the next missing respondent translation into a red build.

**Non-Goals:**

- Creator/editor and billing strings, marketing pages.
- Right-to-left layout for `ar`/`fa`/`he`/`ur`: strings are filled, the page is not mirrored.
- Professional translation review. Catalogs are filled the same way the existing 31 strings were.

## Decisions

### 1. The guard extracts msgids from a fixed list of respondent sources

The test owns a tuple `RESPONDENT_SOURCES` of template and Python paths (survey page, partials it
includes, thanks/password/closed/unavailable/language-select, abuse report pages, public results,
`i18n_extras.py`, `content_screening.py` reasons, `views.py` respondent messages are covered by
wrapping them in templates or `i18n_extras`). Templates go through Django's own
`django.utils.translation.template.templatize`, then a regex over the generated
`gettext(...)`/`pgettext(...)` calls; Python files are parsed with `ast` for `_()`/`gettext()`
calls with literal arguments.

*Alternative:* trust the `#:` location comments in the `.po` files. Rejected — those comments are
written by `makemessages`, and "nobody ran makemessages" is the exact failure we are guarding.

*Alternative:* shell out to `xgettext`. Rejected — adds a system dependency to the test run.

The list is explicit rather than "everything not under `editor/`" because marketing templates live
beside respondent ones in `survey/templates/`. A new respondent template must be added to the list;
the test docstring says so, and a sibling assertion checks that every template the survey page
`{% include %}`s is in the list.

Locales checked: every directory under `survey/locale/` except `en`. An entry counts only when
`msgstr` is non-empty and the entry is not fuzzy.

### 2. Client-side strings travel through the existing channels

- Map hints and control titles → new keys in `i18n_extras.translations` (already exposed to the
  survey page as `var i18n`). Zoom titles via `L.control.zoom({zoomInTitle, zoomOutTitle})`; the
  layers toggle has no title option in Leaflet 1.4, so the title is set on
  `.leaflet-control-layers-toggle` after the control is added.
- Ranking and file upload → `data-msg-*` attributes on the widget root, matching the pattern
  `file_upload.js` already reads but templates never set. JS keeps its English fallback.
- Thanks-page share button → `{% trans %}` into a `json_script`, replacing the ru/ky/en dict.

### 3. One helper activates the survey language

`activate_survey_language(request, survey)` returns and activates, in order: the session's
`survey_language` if the survey offers it; the request's language (`get_language_from_request`) if
the survey offers it; the survey's first language; else leaves the middleware's choice. Called by
the thanks, password-gate, closed/unavailable (wherever `check_survey_access` renders), report and
upload views. It only calls `translation.activate()` for the current request and never writes the
language cookie, so the creator's editor language is untouched (scenario in the delta spec).

The thanks view currently pops `survey_language` before rendering; it reads it first and activates.

### 4. Respondent msgids are added to the catalogs directly, without `makemessages`

Running `makemessages -a` was tried and rejected for two reasons found while doing it:

- The 63 respondent-only catalogs (217 entries each) grew to 2,521 entries of empty editor,
  billing and marketing strings — ~880k lines of diff for nothing a respondent sees.
- In the 11 full catalogs it surfaced ~3,600 untranslated creator/billing msgids and 55 plural
  entries emptied by fuzzy matching, turning `TranslationCatalogHygieneTest` red. That is the
  creator-side gap, out of scope here.

So the merge is textual: a missing respondent msgid is appended to the catalog, an existing
entry with an empty msgstr is filled in place, and nothing else in the file changes (polib's
writer re-wraps every entry). Translations come from per-locale JSON produced by translation
batches and are rejected when their placeholders or HTML tags differ from the msgid's. Two
fuzzy `ky` entries carrying wrong guesses ("Finish drawing" → "Finish editing") were replaced.
The merge script lives outside the repo: it is a one-off, and the guard test keeps the result
honest. `compilemessages` then rebuilds the `.mo` files.

The ru/ky share-button strings from the old `survey_thanks.html` dictionary were carried over
into the catalogs rather than re-translated.

## Risks / Trade-offs

- [LLM translations in 74 languages may be awkward or wrong in rare languages] → short UI strings,
  context given per msgid (where it appears); `ru`, `pl`, `de` spot-read by the owner before merge;
  a customer report is a one-line catalog fix.
- [New entries carry no `#:` location comments] → the next `makemessages` run adds them; nothing
  reads them at runtime, and the guard test extracts from sources, not comments.
- [RTL catalogs filled without RTL layout] → text will render right-to-left within left-to-right
  boxes; still strictly better than English. Layout is a separate backlog item.
- [Guard list drifts as templates are added] → include-graph assertion catches partials of the
  survey page; top-level respondent pages are few and named in the docstring.

## Migration Plan

Catalog and template changes only; no data migration. Deploy is a normal release; rollback is a
revert. `.mo` files ship in the same commit as `.po`.
