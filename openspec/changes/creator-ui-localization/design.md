## Context

Two localization systems already exist in this codebase and must not be confused:

1. **Respondent chrome** (backlog #7, closed 2026-08-10) — Next/Back/Finish, Leaflet.draw
   tooltips, password and thanks pages. 31 strings, compiled across 75 locales, live.
   Its language follows **the survey**, activated per request at `survey/views.py:950`
   from `request.session['survey_language']`.
2. **Survey content translation** — the 75-language picker creators use for their own
   question text. Unrelated to UI strings; see `survey-content-translation`.

This change adds a third, orthogonal axis: the **creator's** UI language. The editor has
zero `{% trans %}` tags across 43 templates, `LANGUAGES` lists only `en`/`ru`, and there
is no switcher or stored preference.

Three findings from reading the current code shape the design:

- **`request.session['_language']` (`survey/views.py:691`) is dead code.** It was
  Django's `LANGUAGE_SESSION_KEY`. On Django 4.2, `get_language_from_request`
  (`django/utils/translation/trans_real.py:560`) resolves language from URL prefix →
  `LANGUAGE_COOKIE_NAME` → `Accept-Language` → `LANGUAGE_CODE`. **The session is never
  consulted.** The write has had no effect since the Django 4 upgrade.
- **The respondent side is therefore already isolated by construction**, but only
  accidentally: `translation.activate()` runs inside the view, after middleware, so the
  view always wins. Nothing states or tests this.
- **`CreatorProfile` is the wrong home for a language preference.** It is documented
  staff-only CRM notes handed over verbatim on a GDPR subject access request; a
  user-controlled setting stored there would read as a staff observation, and its
  "absent means nothing recorded" semantics do not fit a value every user needs.

Constraint from the repo's own conventions: merges reach production within minutes with
no staging gate, so each slice must be independently shippable and reversible.

## Goals / Non-Goals

**Goals:**
- A creator sees the editor, dashboard, auth and account screens in their own language,
  chosen explicitly and remembered across sessions and devices.
- Marketing pages are indexable per language under distinct URLs with a correct
  `hreflang` graph.
- The Russian catalog stops rendering wrong strings.
- Respondent pages keep following the survey's language, provably and under test.

**Non-Goals:**
- Changing respondent chrome behaviour or its 75-locale coverage.
- Translating survey *content* (creators' own question text).
- Prefixing `/editor/` or `/surveys/` URLs — see Decision 2.
- Adding languages beyond the eight named in the proposal.
- Localizing `/admin/` (Django admin, staff-only, English is fine).

## Decisions

### 1. Creator language lives in a new `CreatorPreferences` model, mirrored to the language cookie

A new `CreatorPreferences` model (`OneToOneField` to user, `ui_language` char field,
default `''` = "not chosen"). On login and on every explicit switch, the value is written
to `LANGUAGE_COOKIE_NAME` so `LocaleMiddleware` resolves it with **no per-request DB
query**. Empty preference falls through to `Accept-Language`, then English.

*Alternatives considered.* **Cookie only, no DB** — cheapest (no migration, no model), but
the preference dies with the cookie and on a new device, which lands hardest on exactly
the non-English creators this change serves; it also leaves us unable to segment creators
by language for outreach. **Field on `CreatorProfile`** — rejected above: staff-only CRM
notes with GDPR handover semantics. **Field on `Organization`** — wrong cardinality; two
creators in one org may differ.

*Why a separate model rather than more columns on an existing one:* it creates a home for
future per-creator settings (digest opt-in, timezone) without widening a table whose
meaning is "staff notes".

### 2. `i18n_patterns` wraps only the marketing routes

```python
urlpatterns = [ ... editor, surveys, api, admin ... ]          # never prefixed
urlpatterns += i18n_patterns(
    ... landing + 12 SEO landings + trust + stories ...,
    prefix_default_language=False,
)
```

`prefix_default_language=False` keeps `/` and `/for-planners/` on their current URLs, so
existing rankings and inbound links are untouched; German is served at `/de/for-planners/`.

*Why not prefix everything:* `/surveys/<uuid>/` links are already in respondents' hands
and printed on posters and QR codes; moving them is a breaking change with no upside,
since respondent language comes from the survey, not the URL. `/editor/` is behind auth
and has no SEO value. *Why not skip prefixes entirely (`Accept-Language` only):* Google
would see a single page per URL and index one language — that forfeits the entire SEO
rationale for translating marketing copy.

### 3. Respondent isolation is made explicit and tested, and the dead session write removed

The view-level `translation.activate()` already beats middleware. This design makes that
a stated invariant rather than an accident:

- Delete `request.session['_language'] = ...` at `survey/views.py:691`. It does nothing on
  Django 4.2, and leaving a language-shaped session key around invites a future reader to
  rely on it once a real language cookie exists.
- Add a regression test: a creator whose `ui_language` is `pl` opening a German survey
  gets German respondent chrome.
- Keep `request.session['survey_language']` — it is app-owned, read at
  `survey/views.py:943`, and works.

### 4. Catalogs are merged, never recreated; `ru` creator entries are purged first

`makemessages` merges by `msgid`, so the 31 respondent strings in each of the 75 locales
carry over untouched. The only special step is deleting the ~70 corrupted creator-side
`ru` entries **before** the merge, so they are not preserved as "existing translations".

**Deleting a catalog file to "start clean" is prohibited** — it would regress the one
localization currently serving customers' respondents.

### 5. A test guards against the corruption class that produced the `ru` bug

The `ru` breakage (`Email address` → «Поиск адреса...», `Archived` → «Архитектура») is
mechanically detectable: the same `msgstr` reused for semantically different `msgid`s.
A catalog-hygiene test flags reused `msgstr` values across the eight target locales,
with a small allow-list for legitimate collisions (`Features`/`Capabilities` →
«Возможности»). This is cheap and would have caught the bug before it shipped.

### 6. Marketing copy is authored per language; terminology review is a separate effort

Copy is written directly in each language, not translated, in the **professional register**
of the field — *Bürgerbeteiligung*, *concertation publique*, *konsultacje społeczne* are
what a municipal buyer expects, and a grammatically perfect text with the wrong term reads
as an outsider's.

**Review is out of scope for this change** (owner decision, 2026-08-28). No requests go to
the lead list and no language waits on a reviewer; review will be organised separately.
The earlier plan — recruiting domain-native reviewers from the leads, with paid
marketplaces (Lokalise, Crowdin, Phrase; ~$0.03–0.08/word) as fallback — is recorded here
only as the option that was set aside, not as work this change performs.

*Consequence, stated plainly:* the copy ships on one judgement of register with no
domain-native check behind it. That risk does not disappear by being out of scope, it
just stops being mitigated here. Publishing a language stays a deliberate decision
(`landing-page` spec) so the owner chooses when to accept it, per language.

### 7. Three independently shippable slices

Ordered so the funnel hypothesis is tested before the expensive work:

1. **Brief-language hint** — a line under the AI brief goal field stating the brief may be
   written in any language. No i18n machinery at all. Ships alone, and is the cheapest
   probe of the language-barrier hypothesis that motivated this change.
2. **Creator UI** — wrap the editor, add `CreatorPreferences` + switcher, extend
   `LANGUAGES`, rebuild `ru`, fill the eight catalogs. **`ru` must be rebuilt before the
   switcher is exposed**, or the switcher makes the corruption reachable.
3. **Marketing pages** — `i18n_patterns`, `hreflang`, sitemap rework, per-language copy.
   Per-language rollout; a language goes live only when its `hreflang` and canonicals are
   complete.

## Risks / Trade-offs

- **Respondent page renders in the creator's language** → View-level `activate()` already
  wins; made explicit by Decision 3 plus a regression test. Highest-severity risk because
  it would corrupt customers' respondent experience, not ours.
- **Running `compilemessages` before the catalogs are cleaned** is what actually detonates
  the corruption: the bad entries live only in `.po` and have never been compiled, so
  today's runtime is clean. Compiling would activate a registration form labelled "Search
  address..." *and* an English thanks page reading "Your account has been activated."
  → Catalog cleanup (section 2) is a precondition of every later slice, and the hygiene
  test guards the regression. Established while implementing; the earlier reading blamed
  language reachability, which was wrong.
- **A catalog deleted rather than merged** silently regresses 75-locale respondent
  chrome → Decision 4 prohibition, plus the hygiene test of Decision 5 fails loudly when
  known-good strings vanish.
- **Half-built `hreflang`** is worse for SEO than none → per-language gating in Slice 3;
  a language is absent from the sitemap and the `hreflang` graph until complete.
- **Existing `/` and `/for-planners/` rankings** → `prefix_default_language=False` keeps
  every current URL byte-identical; no redirects are introduced.
- **Volume**: ~14k words of marketing copy per language (~98k total). Mitigated by
  slicing — Slices 1 and 2 carry the product value and do not wait on it.
- **Python 3.9** constrains tooling choices; no dependency in this change requires more.

## Migration Plan

1. Slice 1 ships standalone; no migration, no settings change, trivially revertible.
2. Slice 2: migration adds `CreatorPreferences` (additive, nullable-equivalent default
   `''`). `LANGUAGES` extension is a settings change. Rollback = revert `LANGUAGES` to
   `['en', 'ru']`; the model stays harmlessly. Per repo convention the migration ships in
   its own commit, separate from any `preDeployCommand` change.
3. Slice 3: URL-shape change. Rollback = remove the `i18n_patterns` wrapper; unprefixed
   URLs never moved, so nothing 404s on revert. Localized URLs would 404 after rollback,
   which is why they are only added to the sitemap once their language is complete.

## Open Questions

- Should the language switcher appear on the marketing pages themselves, or only inside
  the editor? A marketing-page switcher needs a visible affordance that does not clutter
  the hero; deferred to Slice 3 design.
- When is each language published? The copy existing does not publish it (see Decision 6
  and the `landing-page` spec) — the owner decides, per language, knowing no domain-native
  review stands behind it.

*Resolved 2026-08-28 by owner decision:* which reviewer to approach per language, and
whether Indonesian ships unreviewed — both moot, terminology review left this change
entirely.
