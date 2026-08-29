# Creator UI localization

## Why

Everything a *creator* sees is English-only. The respondent side was localized in
2026-08 (backlog #7) and stops at the survey page; the editor has **zero** `{% trans %}`
tags across 43 templates, and `LANGUAGES` offers only `en`/`ru` with **no language
switcher and no per-user preference** — so even the Russian catalog is unreachable in
practice.

Two things make this worth doing now:

- **A measured funnel leak.** Of 34 users who registered after AI generation shipped
  (2026-08-10), 23 created a survey and only 11 used the AI draft. The create page —
  including the AI brief panel — is entirely in English, and nothing tells a creator the
  brief may be written in their own language. Non-English creators are a plausible share
  of the 12 who chose "Create empty". This change is the instrumented test of that
  hypothesis, not a bet on it.
- **The buyers we are chasing are non-English institutions.** German municipal buyers
  (ThINK Jena, Berlin Senate) and Polish/French public bodies evaluate tooling partly on
  whether it speaks their language. Combined with EU data-residency friction, an
  English-only product is a second avoidable objection in the same conversation.

Language set (owner decision, 2026-08-26, from creator counts in prod):
**EN + RU, ID, DE, ES, FR, PT, PL** — ~97% of real creators. Indonesian is included
deliberately despite its 30 creators arriving as a single May-2026 course cohort:
cohort channels recur. Russian is included and **rebuilt rather than extended** (see
below). Finnish was evaluated and excluded (3 creators, and Finnish planners read
English natively).

**The Russian catalog is corrupted, not merely incomplete.** Of 215 entries, 101 are
filled, and the creator-side subset contains msgstr values belonging to other msgids:

| msgid | current msgstr | renders as | surface |
|---|---|---|---|
| `Email address` | Поиск адреса... | "Search address..." | registration form |
| `Testing` | Рейтинг | "Rating" | survey status |
| `Archived` | Архитектура | "Architecture" | survey status |
| `Members` | Число | "Number" | organization members |
| `Invitation` | Активация | "Activation" | invitations |

Ten msgstr values are reused across different msgids.

**The root cause is `en`, and the damage is latent rather than live** (established while
implementing, correcting an earlier reading of this section). `en.po` carried 13 entries
whose msgstr paraphrased its own msgid — `Testing` → `Rating`, `Members` → `Number`, and
`Your responses have been recorded.` → `Your account has been activated.` on the
respondent thanks page. `ru` mirrored them, which is how a "translation" came to mean
something else entirely.

None of it was ever compiled into the `.mo` files, so runtime returns the source string
and nothing is broken in production today (`Point` renders as «Точка» from
`django/contrib/gis`, not from us). It goes live the instant this change runs
`compilemessages` — including on the **English** thanks page every respondent sees.
Clearing the catalogs is therefore a precondition of the rest of this change rather than
a nice-to-have, and the reason is compilation state, not language reachability.

## What Changes

- **Editor and creator chrome become translatable.** Wrap user-facing strings across the
  43 editor templates (currently 0 wrapped), plus dashboard, auth, and account screens.
- **A language switcher and a persisted per-user preference.** New field on the user
  profile; the creator's chosen language drives the editor. Falls back to
  `Accept-Language`, then English.
- **`LANGUAGES` grows from 2 to 8** (`en, ru, id, de, es, fr, pt, pl`).
- **Marketing pages get localized URLs.** `i18n_patterns` with
  `prefix_default_language=False` over the landing and the 12 SEO landing pages only:
  `/` stays English, `/de/for-planners/` serves German.
  **`/editor/` and `/surveys/` stay unprefixed** — the editor is behind auth (no SEO
  value) and `/surveys/<uuid>/` links are already in respondents' hands; prefixing them
  would break shared links and is **BREAKING** if done.
- **`hreflang` link tags** on every localized marketing page, plus a self-referencing
  canonical per language.
- **The sitemap emits one entry per language per marketing URL** (~14 URLs × 7). The
  generator is hand-built today and must be reworked.
- **Creator-side translations are written from scratch, not filled in.** Catalogs are
  stale — 217 `msgid` against 840 `{% trans %}` occurrences already in templates. Across
  the 8 target languages there is nothing worth salvaging on the creator side: `de`, `es`,
  `fr`, `pt`, `pl`, `id` have **zero** creator strings translated, and `ru`'s 70 creator
  strings are the corrupted ones. The 70 bad `ru` entries are purged **before** the merge
  so `makemessages` cannot carry them forward.
- **The respondent chrome is preserved untouched.** Each locale holds 31 respondent-facing
  strings (Next/Back/Finish, draw tooltips, password and thanks pages) from backlog #7 —
  live, correct, and compiled across 75 locales; `ru` has all 31 intact and correct.
  Because `makemessages` merges by `msgid`, these carry over automatically. **No catalog
  may be deleted wholesale**, which would regress the one localization already serving
  customers' respondents.
- **Marketing copy is authored per language, not machine-translated**, then validated for
  professional register by a domain-native reviewer (see Impact).
- A hint under the AI brief goal field stating the brief may be written in any language —
  the cheapest probe of the language-barrier hypothesis, shippable ahead of the rest.

## Capabilities

### New Capabilities
- `creator-language-preference`: how a creator's UI language is chosen, persisted,
  switched, and how it is kept from leaking into respondent-facing pages.
- `localized-marketing-urls`: URL scheme, `hreflang`, canonicals, and sitemap emission
  for the multi-language marketing surface.

### Modified Capabilities
- `ui-internationalization`: today it asserts "the system SHALL wrap **all** user-facing
  strings", which the editor has never satisfied — the spec has drifted from reality.
  Requirements change to distinguish the respondent surface (language follows the
  *survey*) from the creator surface (language follows the *user*), and to name the
  supported set. Also corrects a factual drift: the spec requires `LANGUAGE_CODE` to be
  `en-us` while settings say `en`.
- `search-engine-indexing`: the sitemap requirements gain per-language URL emission and
  `hreflang` correctness; the existing "only surveys anonymous visitors can open" rule
  must survive unchanged.
- `landing-page`: the landing gains localized variants and a language affordance.

## Impact

**Code**
- `mapsurvey/settings.py` — `LANGUAGES`, `LANGUAGE_CODE` drift
- `mapsurvey/urls.py`, `survey/urls.py` — `i18n_patterns` over marketing routes only
- `survey/views.py:2075` — `sitemap_xml` is hand-built; needs per-language emission
- `survey/views.py:690,950` — respondent pages force-activate the **survey's** language;
  this must keep winning over any creator preference. Primary regression risk.
- `survey/templates/editor/**` — 43 templates, 0 currently wrapped
- `survey/templates/{landing,for_*,*_alternative,civic_engagement,…}.html` — already
  carry 417 `{% trans %}` tags; these need translation, not wrapping
- `survey/locale/*/LC_MESSAGES/` — regenerate via `makemessages`; 75 dirs exist, 8 matter.
  Purge the 70 corrupted creator-side `ru` entries first; never delete a catalog outright
  (the 31 respondent strings in each of the 75 locales are live).
- New migration: per-user language preference field
- `survey/seo_landings.py` — the 12-entry registry feeds the sitemap

**Translation approach**
Copy is authored directly in each language rather than translated, then reviewed for
*terminology* (not grammar) by a domain-native speaker. Register is the risk:
*Bürgerbeteiligung* / *concertation publique* / *konsultacje społeczne* are the words a
municipal buyer expects, and getting them wrong reads worse than English. Reviewers come
from the existing lead list (ThINK Jena and Berlin Senate for DE, SPEN Gdańsk for PL,
Vaucluse/Laval for FR), which doubles as a re-engagement touch. Paid alternatives
(Lokalise/Crowdin/Phrase review marketplaces, ~$0.03–0.08/word) are the fallback if no
reviewer is available for a language.

**Explicitly out of scope**
- Respondent-facing chrome — already localized, and its language must keep following the
  survey, not the viewer.
- Survey *content* translation (the 75-language creator/respondent picker) — a separate
  system; see `survey-content-translation`.

**Risks**
- Respondent pages rendering in the creator's language instead of the survey's.
- Wiping catalogs "to start clean" would destroy the working 75-language respondent
  chrome. Regeneration must go through `makemessages` merge, never a delete-and-recreate.
- Running `compilemessages` **before** the catalogs are cleaned would activate the
  corruption that is currently latent — a registration form labelled "Search address..."
  and an English thanks page reading "Your account has been activated."
- Existing `/surveys/` and `/editor/` URLs must not move.
- SEO: a half-built `hreflang` graph is worse than none; localized pages must not go live
  before their `hreflang` and canonicals are correct.
- Volume: ~14k words of marketing copy per language, i.e. ~98k across the seven
  non-English languages. Staging matters — the editor and the brief-language hint carry
  the funnel hypothesis and must not wait on the marketing copy.
