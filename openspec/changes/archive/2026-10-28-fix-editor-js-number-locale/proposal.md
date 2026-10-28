# Proposal: fix-editor-js-number-locale

## Why

`USE_L10N = True`, so Django formats numbers in templates for the active locale. **Every one of the
ten non-English creator languages we ship** — de, fr, es, pt, pl, id, nl, it, et, fi — writes
decimals with a comma. English is the only one that does not. Four editor templates interpolate float
coordinates and statistics **straight into inline JavaScript**, unguarded:

```django
var inheritLat = {{ survey.start_map_postion.y|default:"52.52" }};
var lat = hasPosition ? {{ section.start_map_postion.y|default:"52.52" }} : inheritLat;
```

Rendered under a German, French or Dutch UI that becomes

```js
var lat = hasPosition ? 52,5231 : inheritLat;
```

which is not JavaScript. The whole `<script>` block fails to parse, so the map picker never
initialises — for a creator who is not working in English, the "pick the map position" step of both
Section settings and Survey settings is dead.

PostHog has been recording it as three separate issues, all from one creator on Safari:

| Issue | Message | Events |
|---|---|---|
| [`01a04d89`](https://eu.posthog.com/project/248938/error_tracking/01a04d89-1d06-7090-ae52-e02f71958936) | `Unexpected token ','. Expected ':' in ternary operator.` | 9 |
| [`01a051a1`](https://eu.posthog.com/project/248938/error_tracking/01a051a1-66c0-7d71-a64b-a618fae186ca) | `Unexpected number '52'. Expected a parameter pattern or a ')' in parameter list.` | 1 |
| [`01a04d92`](https://eu.posthog.com/project/248938/error_tracking/01a04d92-815d-73e2-99ae-dd78814c57e0) | `Failed to execute 'insertBefore' on 'Node': Unexpected token ','` | 1 |

The first message names the exact construct (`hasPosition ? … : …`) and the second names the exact
number (`52`, the leading digits of our Berlin default `52.52`). They looked like three htmx bugs
because htmx evaluates the scripts it swaps in, so its frames sit on top of the stack.

Reproduced directly:

```
en: var lat = hasPosition ? 52.5231 : inheritLat;
de: var lat = hasPosition ? 52,5231 : inheritLat;
fr: var lat = hasPosition ? 52,5231 : inheritLat;
```

**The respondent side is already protected** — `base_survey_template.html` wraps its map state in
`{% localize off %}` and `survey_section_partial.html` uses `|unlocalize` on its `data-map-*`
attributes. The lesson was learned once, on the surface where it was noticed, and never applied to
the editor. That is why this is a bug about a guard that exists and was not reused, not about a
guard nobody knew about.

The timing matters: the creator-UI localization work is what turned a latent defect into a live one.
The settings comment picks those ten languages from real creator counts — "en 66, id 30, es 15,
fr 12, de 9, pt 7, pl 6 — ~97% of real creators". Roughly a third of our creators are on a language
where the editor's map picker cannot start, and each catalog we complete adds more of them.

## What Changes

- **Wrap each affected inline-JS block in `{% localize off %}`**, the pattern already used by
  `base_survey_template.html`. A block, not a per-value `|unlocalize`, so a coordinate added to the
  block later is covered without anyone having to remember.
  - `editor/partials/section_map_picker.html` — inherit/section lat, lng, zoom
  - `editor/partials/survey_settings_panel.html` — survey lat, lng, zoom
  - `editor/survey_settings.html` — survey lat, lng, zoom
  - `editor/partials/analytics_question_stats.html` — `minVal` / `maxVal` for a numeric question's
    histogram, the same defect on the Responses page
- **Add a guard test** that renders each of these templates under a comma-decimal locale and fails
  if a digit-comma-digit sequence appears inside a `<script>` block. This is what catches the next
  one; the four fixes are a day's worth of value, the guard is the rest.

Human-readable coordinate readouts (`Lat: {{ …|floatformat:5 }}` in the panel headers) stay
localized. They are text for a person, and a German creator should see `52,52` there.

## Capabilities

### Modified Capabilities

- `survey-editor`: numbers the editor emits into JavaScript are machine-readable regardless of the
  creator's UI language.

## Impact

- **Code**: four templates, plus tests in `survey/tests.py`.
- **No migrations, no settings, no URL changes, no Python changes.**
- **English creators see no difference** — `52.52` renders identically with localization off.
- **Not a respondent-facing change.** Respondent map init was already guarded; this PR does not
  touch it.
