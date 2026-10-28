## 1. Russian homepage route

- [x] 1.1 Extract the shared body of `index` and add `index_ru` with `@lang_override('ru')`, `home_path='/ru/'`, `Content-Language: ru`
- [x] 1.2 Route `ru/` → `index_ru` (name `index_ru`) in `survey/urls.py`
- [x] 1.3 `landing.html`: canonical / og_url `https://mapsurvey.org/ru/` when `home_path` is `/ru/`

## 2. Templates

- [x] 2.1 `base_landing.html`: `{% block hreflang %}` defaulting to `en` + `x-default` for `https://mapsurvey.org{{ request.path }}`
- [x] 2.2 `landing.html`: override `hreflang` with the `en` / `ru` / `x-default` triple
- [x] 2.3 Replace the commented `set_language` switcher with EN / RU links shown when `home_path` is set
- [x] 2.4 Brand link and Features / Demo anchors use `home_path`
- [x] 2.5 Footer "Русский" link to `/ru/`

## 3. Sitemap and robots

- [x] 3.1 `_public_base_url(request)` helper: `X-Forwarded-Proto`, then `SITE_URL` scheme for the canonical host, then `request.scheme`
- [x] 3.2 `sitemap_xml` and `robots_txt` use it
- [x] 3.3 Sitemap: `xhtml` namespace, `/ru/` entry, `xhtml:link` alternates on both homepage entries
- [x] 3.4 robots.txt: `Allow: /ru/`

## 4. Translation

- [x] 4.1 `makemessages -l ru` (merge, never regenerate) and list fuzzy / empty msgids used by the three landing templates
- [x] 4.2 Translate every one by hand; unflag fuzzies; keep placeholders and HTML identical
- [x] 4.3 `compilemessages -l ru`; verify with `translation.gettext` under `override('ru')`

## 5. Tests and verification

- [x] 5.1 Tests for every scenario in both delta specs (GIVEN / WHEN / THEN docstrings)
- [x] 5.2 Catalog completeness test for the landing msgids
- [x] 5.3 Run the landing / SEO / i18n test classes, then the full suite once
- [x] 5.4 Open `/` and `/ru/` in a browser on the dev server, read the Russian page end to end, check the switcher and anchors
