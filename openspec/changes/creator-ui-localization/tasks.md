## 1. Slice 1 — brief-language hint (ships standalone)

- [x] 1.1 Add a hint under the AI brief goal field on `survey/templates/editor/survey_create.html` stating the brief may be written in any language
- [x] 1.2 Verify the hint renders on both the desktop merged view and the `<1024px` wizard goal step
- [x] 1.3 Add a PostHog event distinguishing "empty goal → Create empty" from the already-tracked non-empty intercept, closing the measurement blind spot
- [x] 1.4 Run the template guard test immediately after editing the template (multi-line `{# #}` renders as page text)

Notes from doing it:

- `.ai-panel-intro` is hidden by `body.mobile-nav-enabled .ai-panel-intro { display: none }`,
  which is **not** media-query gated — with `MOBILE_EDITOR_NAV` on (the default) that intro
  is invisible at every width, desktop included. A hint placed there would have reached
  nobody. Verified in the browser at 1600px: `display: none`, `offsetParent: null`.
- The hint is deliberately **not** gated on `CREATE_STEER_AI`: it is not part of that
  experiment and must not vanish when the kill switch flips.
- `BriefLanguageHintTest` asserts on the rendered element, not the bare class name — the
  stylesheet ships from `extra_head` regardless of whether a provider is configured, so
  `assertNotIn('ai-lang-hint')` gave a false failure for the no-provider case.
- Browser-verified at 1600×1000 and 390×844: hint visible, below the goal input, within the
  viewport without scrolling; a blank-goal click emits exactly one `blank_goal` event across
  two clicks; a written goal still shows the intercept and emits `shown`.

## 2. Catalog hygiene and the corrupted `ru` entries

- [x] 2.1 Write a catalog-hygiene test that fails when one `msgstr` is reused across semantically different `msgid`s, with an explicit allow-list
- [x] 2.2 Confirm the test fails today against `ru` (it must reproduce `Email address` → «Поиск адреса...», `Archived` → «Архитектура», `Testing` → «Рейтинг», `Members` → «Число», `Invitation` → «Активация»)
- [x] 2.3 Identify the ~70 creator-side `ru` entries and separate them from the 31 respondent-chrome entries, which are correct and must survive
- [x] 2.4 Purge only the corrupted creator-side `ru` entries; do not delete the catalog file
- [x] 2.5 Confirm the 31 respondent strings remain intact in `ru` after the purge

Two corrections to what the proposal assumed, both found by doing this:

- **The corruption is latent, not live.** None of the bad entries were ever compiled
  into the `.mo` files, so runtime returns the source string (or falls through to
  Django's own catalogs — `Point` renders as «Точка» from `django/contrib/gis`, not
  from us). Nothing is broken in production today. It becomes live the moment this
  change runs `compilemessages`, which makes it *our* landmine to clear first, not a
  pre-existing bug to report.
- **`en` is the root cause, and it was not in scope as written.** `en.po` carried 13
  entries whose msgstr paraphrased their own msgid — `Testing` → `Rating`,
  `Members` → `Number`, and `Your responses have been recorded.` → `Your account has
  been activated.` on the respondent thanks page. `ru` mirrored them, which is how a
  "translation" came to mean something else entirely. Blanked all 13 so gettext
  returns the source.

Scope therefore ran wider than 2.4 describes: 13 `en` entries blanked, 26 `ru`
entries rewritten — including one respondent-chrome string (`Your responses have been
recorded.`), so the claim in 2.3/2.5 that the respondent set was uniformly correct was
wrong. All 31 respondent ids remain present in `ru` and the thanks page now reads
«Ваши ответы сохранены.»

The hygiene test catches the mechanical signature only: one `msgstr` serving several
`msgid`s. A unique-but-wrong translation passes it — which is exactly how the thanks
page slipped through. Semantic correctness still needs a reader, and that is what the
terminology review in section 8 is for.

## 3. Wrap creator-facing templates

- [ ] 3.1 Wrap user-facing strings in the 43 templates under `survey/templates/editor/` with `{% trans %}` / `{% blocktrans %}`
- [ ] 3.2 Wrap registration, login, activation and account templates
- [ ] 3.3 Wrap creator-facing strings in `survey/templates/editor.html` and dashboard partials
- [ ] 3.4 Leave machine-readable values and developer-facing strings unwrapped
- [ ] 3.5 Leave `/admin/` untouched (staff-only, out of scope)
- [ ] 3.6 Run `makemessages` and confirm it merges rather than recreates — the 31 respondent strings must carry over in all 75 locales untouched

## 4. Creator language preference and switcher

- [ ] 4.1 Add a `CreatorPreferences` model with a `OneToOneField` to user and a `ui_language` field defaulting to `''`; do **not** add the field to `CreatorProfile`
- [ ] 4.2 Generate the migration; ship it in its own commit, separate from any `preDeployCommand` change
- [ ] 4.3 Check the migration number against other worktree branches before merge (parallel migration collisions)
- [ ] 4.4 Mirror the stored preference into `LANGUAGE_COOKIE_NAME` on login and on switch, so `LocaleMiddleware` resolves it without a per-request DB query
- [ ] 4.5 Implement resolution order: stored preference → `Accept-Language` → English, with unsupported values falling back rather than erroring
- [ ] 4.6 Build the language switcher listing exactly the eight supported languages, each written in its own language
- [ ] 4.7 Extend `LANGUAGES` in `mapsurvey/settings.py` from 2 to 8 (`en, ru, id, de, es, fr, pt, pl`)
- [ ] 4.8 Correct the `LANGUAGE_CODE` spec drift (`en-us` in spec vs `en` in settings)

## 5. Respondent isolation

- [ ] 5.1 Delete the dead `request.session['_language'] = ...` write at `survey/views.py:691` (Django 4.2 never reads it)
- [ ] 5.2 Keep `request.session['survey_language']`, which is app-owned and read at `survey/views.py:943`
- [ ] 5.3 Add a regression test: a creator whose preference is `pl` opening a German survey gets German respondent chrome
- [ ] 5.4 Add a regression test for the editor's Live preview iframe, which serves a respondent page from under `/editor/`
- [ ] 5.5 Verify respondent chrome coverage is unchanged across all 75 locales after catalog regeneration

## 6. Creator UI translations (Slice 2 completion)

- [ ] 6.1 Author Russian creator-side strings from scratch (the purged entries), not by filling the old ones back in
- [ ] 6.2 Author creator-side strings for `de`, `es`, `fr`, `pt`, `pl`, `id`
- [ ] 6.6 Leave every marketing msgid empty in all catalogs (sections 7–8 deferred) so those pages fall back to English rather than rendering half-translated
- [ ] 6.7 Clear fuzzy entries after every `makemessages`: gettext guesses by string similarity, and that is what produced `Signal` → «Войти» and `Stars` → «Начать». An empty msgstr falls back honestly; a fuzzy one lies as soon as the flag is dropped
- [ ] 6.8 Clear fuzzy with `polib`, never with a regex over the raw `.po`

Two process notes, both learned the hard way here:

- **The catalog header carries `#, fuzzy` itself.** A regex sweep for fuzzy entries
  matched it and blanked its msgstr — which is where `Content-Type: charset=UTF-8`
  lives. Six catalogs then failed `makemessages` with "input file doesn't contain a
  header entry with a charset specification", and only `ru`/`en` (whose headers were
  real, not template stubs) survived. `polib` keeps the header in `po.metadata`,
  outside the entry iteration, so clearing fuzzy through it cannot repeat this.
  Headers were rebuilt with per-language `Plural-Forms`.
- **Re-running `makemessages` costs hand-written corrections.** It re-marks moved
  entries fuzzy, and the fuzzy sweep then blanks them. Extract once after the
  templates are wrapped, then translate; do not re-extract while filling catalogs.
- [ ] 6.3 Compile catalogs and confirm the hygiene test from 2.1 passes for all eight languages
- [ ] 6.4 Verify the switcher renders each language end-to-end in the editor
- [ ] 6.5 Confirm `ru` is rebuilt **before** the switcher is exposed to users

## 7. Slice 3 — localized marketing URLs — **DEFERRED**

**Sections 7 and 8 are deferred out of this change** (owner decision, 2026-08-28): ship
the creator interface, hold the marketing surface. The two sections are one unit — URL
prefixes, `hreflang` and per-language sitemap entries exist only to serve translated
marketing pages, and `/editor/` is behind auth and never prefixed, so nothing in the
shipped interface depends on them.

What this means concretely: the marketing msgids stay **empty** in every catalog, so the
landing and SEO pages keep rendering English for everyone. That is the honest fallback —
an empty translation shows the source string, it does not show a gap. No URL moves, no
`hreflang` is emitted, and the sitemap is untouched.

Measured split of the 1317 extracted strings, which is what makes the cut clean:
**777 interface strings (3509 words) ship; 540 marketing strings (5557 words) wait.**

- [ ] 7.1 Wrap the remaining unwrapped marketing strings (the landing pages already carry 417 `{% trans %}` tags)
- [ ] 7.2 Apply `i18n_patterns(..., prefix_default_language=False)` to marketing routes only
- [ ] 7.3 Verify `/editor/`, `/surveys/<uuid>/` and `/r/<slug>/` remain unprefixed and do not redirect
- [ ] 7.4 Emit `hreflang` sets and self-referencing canonicals on localized marketing pages, excluding unpublished languages
- [ ] 7.5 Rework `sitemap_xml` (`survey/views.py:2075`) to emit one entry per published language for marketing URLs only
- [ ] 7.6 Confirm the sitemap still routes survey entries through the shared publicly-visible function, unchanged
- [ ] 7.7 Add the language affordance to marketing pages, keeping the visitor on the same page when switching
- [ ] 7.8 Add a test asserting no `/surveys/<uuid>/` entry carries a language prefix

## 8. Marketing copy per language — **DEFERRED** (see section 7)

- [ ] 8.1 Author landing and SEO-page copy per language (~14k words each), written in-language rather than translated
- [ ] 8.2 Publish each language only once its copy, canonical and `hreflang` wiring are all complete

**Terminology review is out of scope for this change** (owner decision, 2026-08-28): no
review requests go to the lead list, and no language waits on a reviewer. Review will be
organised separately.

Dropped from this section as a result: sending reviewer requests, applying reviewer
corrections, and the open question on whether Indonesian ships unreviewed — that question
no longer has a gate to sit behind.

The risk this leaves standing, unchanged and now unmitigated within this change: copy
ships in the professional register I judged right, without a domain-native check. For
German municipal readers especially, the wrong term for public participation reads worse
than English. Publishing timing (8.2) is where that judgement gets made, and it is the
owner's call, not a checklist item.

## 9. Verification

- [ ] 9.1 Run `./run_tests.sh survey -v2` and record the delta against a pre-change baseline
- [ ] 9.2 Drive the editor in a real browser per language — a dead control passes every Django test
- [ ] 9.3 Verify a German survey opened by a Polish-preference creator renders German respondent chrome, in the browser
- [ ] 9.4 Fetch `/sitemap.xml` and confirm every advertised localized URL returns 200
- [ ] 9.5 Confirm the rollback path: reverting `LANGUAGES` to `['en', 'ru']` leaves the site serving English with no 404s
