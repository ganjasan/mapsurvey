## Context

`/` is served by `views.index`, decorated `@lang_override('en')`: the page is always English whatever the visitor's `Accept-Language`, because `LANGUAGES` is the creator-interface list and the marketing pages were deferred. The templates (`landing.html`, `base_landing.html`, `partials/_story_card.html`) already wrap every visible string in `{% trans %}`. The `ru` catalog exists but covers 159 of ~1470 msgids, and `ru` is deliberately absent from `LANGUAGES`.

Search engines do not send `Accept-Language` and do not keep cookies, so a language version has to live at its own URL and be declared with `hreflang`.

## Goals / Non-Goals

**Goals:**
- A crawlable Russian homepage at a stable URL, fully translated, declared to Google as the `ru` alternate of `/`.
- `hreflang` on every marketing page, so the English pages are explicitly the version for every other locale (`x-default`).
- `https` URLs in the sitemap and robots.txt on production.

**Non-Goals:**
- Russian versions of the audience pages, Pro, Services, Trust, stories, registration or the editor.
- Adding `ru` to `LANGUAGES`.
- Language auto-detection or redirects.

## Decisions

**Prefix route `ru/` plus `translation.override('ru')`, not `i18n_patterns`.** `i18n_patterns` would prefix every URL in the include and pull the editor into URL-based language selection, which the creator-language design forbids. A single `path('ru/', views.index_ru)` with `@lang_override('ru')` reuses the same view body. `translation.activate`/`override` resolves against the catalog on disk and ignores `LANGUAGES`, which `settings.py` documents and the respondent pages already depend on.

**`Content-Language` set explicitly.** `LocaleMiddleware.process_response` writes `Content-Language` from the language active *after* the view returns, which is the request language again once the override exits. `index_ru` sets the header itself.

**`hreflang` as a template block with a `request.path` default.** `base_landing.html` gets `{% block hreflang %}` whose default emits `en` and `x-default` for `https://mapsurvey.org{{ request.path }}`, matching how every page writes its canonical. `landing.html` overrides it with the full `en`/`ru`/`x-default` triple, identical on both URLs, as Google requires reciprocal sets. The host is hardcoded like the canonicals are; previews are `noindex`-irrelevant here because their canonical already points to production.

**Home-relative links via a context variable.** `index` passes `home_path='/'`, `index_ru` passes `home_path='/ru/'`; the navbar brand and the `#features` / `#demo` anchors use `{{ home_path|default:'/' }}`, so other pages keep linking to `/`.

**Switcher as plain links.** The commented-out `set_language` form switched a cookie on the same URL, which crawlers cannot follow. The new switcher is two links (`/` and `/ru/`) shown only on the homepage pair; the footer of every marketing page carries one "Русский" link to `/ru/` (written in Russian, untranslated, so a Russian reader recognises it on an English page).

**Scheme from `X-Forwarded-Proto`, then `SITE_URL`.** Behind Cloudflare and Render, `request.scheme` is `http`. Setting `SECURE_PROXY_SSL_HEADER` would change `request.is_secure()` for CSRF, cookies and redirects site-wide, which is out of proportion for this fix. A small helper `_public_base_url(request)` takes `X-Forwarded-Proto` when present; otherwise, if the host equals `SITE_URL`'s host, it uses `SITE_URL`'s scheme; otherwise `request.scheme` (local dev, tests).

**Translation quality.** Strings are translated by hand as marketing copy, not word-for-word, using the terms Russian-speaking planners use (опрос, анкета на карте, соучаствующее картографирование, муниципалитет). Brand and format names (Mapsurvey, GeoJSON, QGIS, Excel) stay as-is. Placeholders and HTML in `blocktrans` are kept byte-identical. Any `#, fuzzy` entry the merge produces for these msgids is rewritten and unflagged.

## Risks / Trade-offs

- **Stories carousel shows English story text on `/ru/`** (titles and summaries are database rows). Accepted: the section heading and buttons are Russian; translating stories is a separate decision.
- **CTAs lead to English pages** (registration, audience pages). Accepted for this change; the creator UI joins `LANGUAGES` as Russian only when its catalog is complete.
- **A wrong translation passes tests.** `TranslationCatalogHygieneTest` only catches structural faults. Mitigation: a test asserts that every msgid rendered on `/ru/` has a non-empty, non-fuzzy translation, plus a manual read of the rendered page.
- **Compiling `ru` activates every existing `ru` msgstr site-wide** wherever `ru` is activated (respondent chrome for Russian surveys). The catalog was audited and fixed in August (`lesson-ru-locale-catalog-corrupted`); the hygiene test still runs.

## Migration Plan

Deploy is code-only. After deploy: request indexing of `/ru/` in Search Console and resubmit the sitemap. Rollback is a revert; `/ru/` then 404s, which Google drops on its own.

## Relation to the deferred marketing-localization slice

`creator-ui-localization` deferred localized marketing URLs (its sections 7–8) with the plan `i18n_patterns(..., prefix_default_language=False)`, which would put Russian at `/ru/…`. This change claims exactly `/ru/` for the homepage, so that plan can later take the route over without moving any URL. Its rule that a language joins the `hreflang` graph only once its pages are complete holds here: `ru` is declared only on the homepage pair, which this change translates in full.
