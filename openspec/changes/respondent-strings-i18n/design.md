## Context

`survey/locale/` holds 75 catalogs, one per language a creator can offer respondents. Strings
from before September 2026 are translated in 69–71 of them; later strings were translated only in
the ~10 languages the creator UI is offered in, or in none. `TranslationCatalogHygieneTest`
guards creator surfaces in those offered languages only, by matching template paths. A
respondent page also pulls strings from Python (the `i18n` JSON on `<body>`,
`survey/templatetags/i18n_extras.py`) that a template scan cannot see.

## Goals / Non-Goals

**Goals:** every respondent-facing interface string translated in all 75 catalogs; a test that
keeps it so for the next string.

**Non-Goals:** creator surfaces, marketing pages, public results `/r/`, e-mails; the quality of
existing translations; survey content (creator-authored, already per-language).

## Decisions

- **Record lookups, do not scan templates.** The guard wraps the gettext functions on
  `django.utils.translation._trans` (the proxy every `{% trans %}` and `gettext()` goes
  through) while the test client renders the pages, and keeps the msgids it saw. This catches Python strings and partials pulled in by `{% include %}`, and it
  skips branches a respondent never reaches (the signed-in account menu in `base.html`). A
  template scan was the alternative; it over-reports creator chrome and misses Python strings —
  the two failure modes recorded after the August 2026 i18n work.
- **Only our msgids, read from the compiled catalogs.** A msgid is ours when one of our `.po`
  files names it (filled or not) or our source writes it literally; the catalogs alone cannot
  say, because a string nobody ran `makemessages` for is in none of them — exactly the case the
  test is for. The check reads the `.mo` files through the stdlib `gettext`, which is what runs:
  a fuzzy entry never reaches them.
- **Catalogs without a `Plural-Forms` header** (am, gu, ky, lo, no, si, tl, zh) get the CLDR one,
  because `msgfmt` refuses a plural entry without it.
- **Fixture covers the features, not a copy of a customer survey.** One survey with two
  languages (language choice page), a map section with point/line/polygon/spray, a tap-to-place
  point whose pop-up has an icon-grid choice, a collapsible group and a thumbs question, a form
  section with choice/multichoice/rating/number/text, a required question posted empty
  (validation message), the thanks page and the report form.
- **Translations are authored, then checked mechanically.** Each new msgstr keeps the msgid's
  placeholders (`%(n)s`) and the plural forms of the catalog's `Plural-Forms`; `msgfmt --check`
  runs on every catalog.

## Risks / Trade-offs

- [Machine-quality translations in rare languages] → same standard as the existing 69–71/75
  strings; short UI phrases; a wording fix is a one-line catalog edit.
- [Guard misses a respondent surface the fixture does not reach] → the fixture lists features
  explicitly; a new respondent feature adds itself to the fixture in its own change.
- [Test runtime] → one survey, about ten requests, catalogs parsed once per test class.
