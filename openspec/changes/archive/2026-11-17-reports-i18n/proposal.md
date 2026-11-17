## Why

The Reports epic (#712) added about 260 creator- and reader-facing strings — the Reports list and start
page, the report editor, the "Before you publish" dialog, the public report page and its PDF, the analysis
views in Data — and none of them is in the ten catalogs the interface is offered in. A German or Finnish
creator would open Reports and read English between translated menus. The epic's PRs carried this as a
debt to pay once, after the screens stopped changing.

## What Changes

- The epic's strings are translated in the ten offered catalogs (`de`, `fr`, `es`, `pt`, `pl`, `id`, `nl`,
  `it`, `et`, `fi`), appended by hand as in earlier changes (no `makemessages` rewrite), and compiled.
- A guard: every literal string the Reports screens ask gettext for is translated in every offered
  language, so a string added to Reports later cannot ship English-only unnoticed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ui-internationalization`: a new requirement — the Reports module's strings are translated in every
  offered language.

## Impact

- `survey/locale/<10 languages>/LC_MESSAGES/django.po` and `.mo`.
- `survey/tests/test_ui_internationalization.py` (the guard).
- No code path, model or template changes.
