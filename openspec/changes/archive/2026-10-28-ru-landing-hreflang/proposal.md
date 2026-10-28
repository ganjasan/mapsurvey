## Why

Google drops mapsurvey.org from brand results (`mapsurvey`, `mapsurvey.org`) for people searching with a Russian-language Google interface in CIS countries, while it ranks #1 everywhere else (issue #248). The site carries no language signal beyond `lang="en"`, so for that audience Google prefers Russian and local documents. The owner considers the CIS a real audience, so the fix is a Russian homepage plus explicit `hreflang`, not only a signal tweak. The same audit found the sitemap and robots.txt advertising `http://` URLs while every canonical is `https://`.

## What Changes

- New public page `/ru/`: the homepage rendered in Russian from the existing `{% trans %}` strings, with its own canonical, `<html lang="ru">` and `Content-Language: ru`.
- A complete `ru` translation of every string the homepage, its base template and its story card render.
- `hreflang` alternates on every page built on `base_landing.html`: the homepage pair carries `en`, `ru` and `x-default`; every other marketing page carries `en` and `x-default` pointing at itself.
- An EN / RU switcher in the homepage navbar, and a "Русский" link in the shared footer, so people and crawlers reach `/ru/`.
- Same-page anchors and the brand link on `/ru/` stay on `/ru/` instead of jumping to the English homepage.
- `sitemap.xml` and the `Sitemap:` line in `robots.txt` use the scheme the visitor actually used (`X-Forwarded-Proto`, falling back to `SITE_URL` for the canonical host), so production emits `https://`.
- `sitemap.xml` lists `/ru/`, and both homepage entries carry `xhtml:link` alternates; robots.txt allows `/ru/`.

Not changing: `ru` stays out of `LANGUAGES` (the creator catalog is not complete), the other marketing pages stay English-only, no redirect by `Accept-Language`.

## Capabilities

### New Capabilities
- `landing-page-localization`: the Russian homepage at `/ru/`, the language alternates (`hreflang`) on marketing pages and the language switcher.

### Modified Capabilities
- `search-engine-indexing`: the sitemap and robots.txt advertise the canonical `https` scheme and list the Russian homepage with its alternates.

## Impact

- `survey/views.py`: new `index_ru` view; `index` rendering shared; `robots_txt` and `sitemap_xml` build URLs from a scheme helper.
- `survey/urls.py`: `ru/` route.
- `survey/templates/base_landing.html`, `survey/templates/landing.html`: `hreflang` block, switcher, home-relative anchors, footer link.
- `survey/locale/ru/LC_MESSAGES/django.po` / `.mo`: landing strings translated.
- `survey/tests.py`: new tests.
- No models, no migrations, no new settings, no new dependencies.
