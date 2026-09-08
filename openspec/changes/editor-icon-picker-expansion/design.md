## Context

`Question.icon_class` is a free-text `CharField(80)` holding a Font Awesome 5 class
(`fas fa-bus`). The editor wraps that input with a picker built inline in
`editor/partials/question_form_modal.html`: an `FA_ICONS` array of ~180 classes and a search
that substring-matches the class name. Every surface that draws the icon does so by putting the
stored string into a `class` attribute:

| Surface | Where | How |
|---|---|---|
| Respondent map marker | `L.Icon.FontAwesome.js` `_createIcon` | `<span class="{iconClasses} feature-icon">` inside the pin SVG |
| Crosshair overlay (place / edit) | `base_survey_template.html` `showCrosshair` | `iconEl.className = 'crosshair-pin-icon fa ' + iconClass` |
| Draw button card | `leaflet_draw_button.html` | `<i class="{{ widget.draw_icon_class }}">`, `data-icon` on the button |
| Star rating | `partials/rating_stars.html` via `Question.star_icon()` | `<i class="{{ field\|star_icon }}">` |
| Editor picker preview | modal JS | `<i class="' + val + '">` |
| AI generation | `survey/ai/materialize.py` | `'fas fa-%s' % icon` from a curated enum |

Three of them prepend a legacy `fa ` to a string that already starts with `fas`/`far`; it is
harmless for Font Awesome and will break anything that is not a class list. The Responses map
and the public results map draw `circleMarker`s and never read the icon, so they are out of
this change despite the proposal listing them.

Font Awesome is loaded from the CDN at 5.8.1 in three base templates. Font Awesome Free 5.15.4
ships `metadata/icons.json` (label, `search.terms`, styles) and `metadata/categories.yml`. Maki
(`mapbox/maki`) and Temaki (`rapideditor/temaki`) ship one SVG per icon with descriptive
file names and, for Temaki, a small `data/icons.json` of names and tags. All three are
redistributable (CC BY 4.0 with the notice already in the CSS; CC0; CC0).

Product languages for creator-facing text are EN, RU, DE, ES, FR, PT, PL, ID (see
`survey-content-translation` and the language memory). Django `LANGUAGES` for the UI is only
EN/RU; the picker must not depend on the UI catalog for its search terms.

## Goals / Non-Goals

**Goals:**
- A creator finds an icon by typing a word in their language, or by browsing a theme, without
  knowing Font Awesome naming.
- Every free Font Awesome 5 icon (solid + regular) plus the Maki and Temaki map sets are
  available.
- Exactly one place resolves `icon_class` to a drawn glyph, on the server and in the browser,
  so no surface can render a `maki:` value as a broken class string.
- Zero-result searches are measured.
- Existing stored values render pixel-identically; no migration.

**Non-Goals:**
- Font Awesome 6 (renames half the classes; would need a compatibility layer for stored values).
- Runtime translation, AI-assisted search, or suggestions from the question title.
- Custom uploaded icons.
- Widening the AI generation enum.
- Icons on the Responses map or public results map (they do not draw question icons today).

## Decisions

### D1. One generated catalog file, lazy-loaded, built by a checked-in script

`scripts/build_icon_catalog.py` reads vendored upstream metadata and writes
`survey/assets/data/icon_catalog.json`:

```json
{
  "version": "fa-5.15.4 maki-8.x temaki-5.x",
  "categories": [{"id": "transport", "label": {"en": "Transport", "ru": "Транспорт", ...}}, ...],
  "icons": [
    {"v": "fas fa-bus", "l": "Bus", "c": ["transport"],
     "t": {"en": "bus machine public transportation vehicle", "ru": "автобус транспорт ...", ...}},
    {"v": "maki:bench", "l": "Bench", "c": ["map", "amenities"], "t": {...}},
    ...
  ]
}
```

- `v` is the exact value written to `icon_class`; `t` is one lowercase space-joined string per
  language (search is a substring test on the query's language string plus English, so a
  creator on the German UI typing `bus` still finds it).
- The file is a normal static asset: WhiteNoise hashes and gzips it, the picker learns its URL
  from a `data-icon-catalog` attribute rendered with `{% static %}`, and fetches it on first
  open, once per page. Nothing loads for creators who never open the picker.
- Upstream inputs (FA `icons.json` + `categories.yml`, Maki and Temaki SVG directories) are
  **not** vendored; the script takes their paths as arguments and the generated JSON plus the
  sprites are what is committed. Refreshing the set is "download upstream, run script, commit".
  The script prints icon counts so a shrunken catalog is visible in review.

*Alternatives*: shipping FA's own `icons.json` (2 MB, wrong shape, English only); a server
endpoint (a request per keystroke for static data); vendoring upstream repos (three vendored
trees for one JSON).

### D2. Translations are a checked-in table authored in this change, merged at build time

`scripts/icon_terms.<lang>.json` maps an English term (as it appears in FA `search.terms`, Maki
and Temaki names, and every icon label) to a list of terms in that language. The build script
joins them; an English term with no entry contributes only its English form. The seven tables
are written by Claude during implementation (owner decision 2026-09-09), reviewed as data, and
edited by hand afterwards like any other file. Terms are translated per **term**, not per icon,
so ~2,500 unique strings cover ~2,100 icons, and a fix to "bench" fixes every bench.

Quality bar: a term list is a search index, not copy. Multiple synonyms per entry are
encouraged (`bench` → `скамейка скамья лавочка`), inflected forms are unnecessary because
matching is substring on the stem the creator types.

*Alternative*: translating at build time through Gemini (non-deterministic output in a
committed file; a paid call in a build step).

### D3. `icon_class` gets a second value form: `maki:<name>` / `temaki:<name>`

Font Awesome values stay exactly as they are. SVG-set values are `<set>:<name>`, matching the
sprite symbol id. The model field, its `max_length`, and the DB are untouched.

Server validation (`QuestionForm.clean_icon_class`): a value is valid when it is empty, matches
`^(fas|far|fab|fa) fa-[a-z0-9-]+$`, or is `<set>:<name>` present in the catalog. Font Awesome
is regex-only so that old rows (v4 `fa fa-x` names, Pro classes a creator pasted) keep saving;
SVG names are catalog-checked because a typo there would render the fallback pin silently. The
catalog is loaded once per process by `survey/marker_icons.py` (`lru_cache` over the static
file) and exposes `is_known(value)` and `resolve(value)`.

### D4. One resolver on each side; every surface goes through it

**Python** — `survey/marker_icons.py`:

```
resolve(value) -> {"kind": "font", "classes": "fas fa-bus"}
               | {"kind": "svg",  "symbol": "maki-bench"}
```

plus a template tag `{% marker_icon value color=... css_class=... %}` that renders either
`<i class="… {css_class}" style="color:…">` or `<svg class="{css_class}" style="fill:…"><use
href="{sprite}#{symbol}"/></svg>`. The tag replaces the `<i>` in `leaflet_draw_button.html`
and `rating_stars.html` (`Question.star_icon()` keeps returning the raw value; the tag draws
it).

**JavaScript** — `survey/assets/js/marker_icon.js` (`window.MarkerIcon.resolve(value)`,
`.element(value, color, cssClass)`), loaded by `base_survey_template.html` and
`editor_base.html`. It is the only code that knows about the `fa ` legacy prefix, so the three
`'fa ' + icon` concatenations are deleted rather than each learning about SVG.

- `L.Icon.FontAwesome._createIcon` calls `MarkerIcon.element(options.iconClasses,
  options.iconColor, 'feature-icon')`. The CSS for `.feature-icon` gains a `svg` sibling rule
  (16×16, `fill: currentColor`, same `top: 8px`, centred) so a Maki glyph sits where a Font
  Awesome glyph sits; the comment in `L.Icon.FontAwesome.css` about keeping in sync with
  `.crosshair-pin-icon` extends to both.
- `showCrosshair` and the popup-edit path replace the overlay's icon node with
  `MarkerIcon.element(...)` instead of assigning `className`.
- The editor picker preview and grid cells use `MarkerIcon.element`.

**Fallback**: an unknown `<set>:<name>` resolves to `{"kind": "font", "classes": "fas
fa-map-marker-alt"}` on both sides. A Font Awesome-shaped string is passed through untouched,
as today, even if the catalog has never heard of it.

### D5. Sprites: one SVG symbol sheet per set, referenced by `<use href>`

`survey/assets/img/maki.svg` and `temaki.svg`, generated by the build script from the upstream
SVG directories: each icon becomes `<symbol id="maki-bench" viewBox="0 0 15 15">…</symbol>`
with `fill` attributes stripped so `currentColor`/CSS fill applies. Maki is 15×15, Temaki
15×15 as well; the symbol keeps its own `viewBox` so the drawing size is set by CSS alone.
External `<use href="…#id">` is same-origin here (static is served from the app host) and is
supported by every browser we serve. The sprite URL is rendered once into a `data-icon-sprites`
attribute on `<body>` (a small JSON `{maki: url, temaki: url}`) so the JS resolver never
hard-codes a static path that WhiteNoise has hashed.

*Alternative*: inlining the sprite into every page (~150 KB on every respondent page for a
feature most surveys will not use).

### D6. Picker rewritten as `survey/assets/js/icon_picker.js`

Extracted from the modal's inline script; the modal keeps a one-line `IconPicker.attach(input,
{catalogUrl, lang})`. Behaviour:

- Header: search input, then a horizontal row of category chips (`All`, the product categories,
  `Map`) — chips, not tabs, so they wrap on the 768px editor mobile layout. Category labels come
  from the catalog in the creator's UI language, falling back to English.
- Search matches on `t[lang] + ' ' + t.en + ' ' + label + ' ' + name`; each whitespace-separated
  query token must match (so `bus stop` narrows, not widens). Category and query combine.
- The grid renders at most 240 cells and shows "Type to narrow" beyond that. With no query and
  `All`, the first cells are the current value, then the Map set, then Font Awesome by category
  order — the map icons are what most creators come for.
- Selecting a cell writes `v` to the input and dispatches `input` (autosave and live preview
  already listen for it).
- Telemetry: `icon_search_miss` `{query, lang, category}` once per distinct query, sent 700 ms
  after the last keystroke that leaves zero results; `icon_picked` `{value, set, via}` where
  `via` is `search`, `browse`, or `typed`. Both guarded by `window.posthog && posthog.capture`
  like the other editor events.

### D7. Categories: a product mapping over Font Awesome's, not Font Awesome's own

FA's `categories.yml` has ~55 categories tuned for a web-UI audience (Accessibility, Alert,
Code, Currency, …). The build script maps them onto ~12 product categories (`transport`,
`nature`, `buildings`, `people`, `safety` (hazards, problems, warnings), `amenities`,
`health`, `sport`, `shopping`, `objects`, `shapes`, `other`) via a table in the script; an FA
icon can be in several. Maki and Temaki icons get `map` plus a product category from a
name-keyword table in the same script. Anything unmapped lands in `other`, never dropped.

### D8. Font Awesome 5.8.1 → 5.15.4 in the three base templates

Same major, same class names, ~200 more icons, and the catalog is generated from 5.15.4
metadata so the picker never offers a glyph the stylesheet cannot draw. The `FA_ICONS` list
in the modal and its duplicate knowledge in `question_types.py` comments are removed.

## Risks / Trade-offs

- [Catalog size: ~2,100 icons × 8 languages of terms ≈ 1 MB raw] → substring-joined strings
  instead of arrays; WhiteNoise gzip lands ~150–200 KB; lazy fetch on first open only; measured
  in the tasks with a size ceiling asserted by a test (fail the build past 350 KB gzipped so
  a translation table cannot balloon unnoticed).
- [Translation quality is unreviewable at 2,500 × 7] → per-term tables are diffable and
  correctable one line at a time; the miss telemetry is the review loop: a term creators
  type that yields nothing is a missing row.
- [Maki/Temaki glyphs are simpler and heavier than FA glyphs at 16 px] → sprite symbols keep
  their viewBox, CSS size is shared with `.feature-icon`; a visual check of both sets inside
  the pin at 1× and 2× DPR is a task.
- [A pasted Pro or unknown FA class] → unchanged from today: rendered as an empty glyph on a
  coloured pin. Not solved here; the picker makes it rarer.
- [Search on Russian/Polish inflection] → substring on the stem the creator types is enough for
  nouns; verbs and adjectives are not search terms.
- [`<use href>` to an external sprite and Safari] → supported since Safari 12; the fallback pin
  covers the rest.
- [Editor page weight] → `icon_picker.js` and `marker_icon.js` are small; the catalog is not
  loaded until the picker opens.
- [Existing `crosshair-pin-icon` and `.feature-icon` positioning tuned for glyph fonts] →
  new `svg` sibling rules mirror the same offsets; one screenshot each for FA and Maki
  during verification.

## Migration Plan

1. Land the build script, the translation tables, the generated catalog and sprites, the
   resolver (both sides), and the picker in one PR. No data migration; existing rows keep
   rendering because Font Awesome values are passed through.
2. Deploy is a normal static deploy (`collectstatic` already runs). The CDN bump is a template
   change; if 5.15.4 misbehaves the link is reverted independently of everything else.
3. Rollback: revert the PR. Any survey that already stored a `maki:`/`temaki:` value would then
   render a blank glyph on the pin (the string lands in a `class` attribute) — same failure
   mode as an unknown FA class today, and not a data loss; re-deploying restores it.

## Open Questions

- Temaki's `data/icons.json` tags exist for some icons only; the script treats missing tags as
  "name split on hyphen". Fine for v1, may need a hand-authored keyword table if telemetry
  shows Temaki misses.
- Whether to keep `fab` (brands) in the catalog: excluded by default — brand logos are not
  marker icons and the CC BY licence explicitly disallows using them to imply endorsement.
  Still accepted by validation if pasted.
