## Context

Four creator-facing templates embed a Leaflet map in an inline `<script>`:
`editor/layer_editor.html`, `editor/partials/survey_settings_panel.html`,
`editor/partials/section_map_picker.html`, `editor/survey_settings.html`. Each
interpolates server-side values into JavaScript and each attaches behaviour to a map
that HTMX may swap out from under it.

That shape has now broken three times in three weeks, always in a way no English-language
test run reproduces:

| When | What broke | Fixed by |
|---|---|---|
| 2026-08-30 | decimal comma in three templates | `e2ba265`, guard pinned to two URLs |
| 2026-09-04 | decimal comma in the fourth template (`#155`) | — live |
| 2026-09-16 | `null` dereference in all three pickers (`#192`) | — live |

The August fix is the instructive one. It was correct, it shipped with tests, and it did
not prevent the September recurrence — because the test asserted *"these two URLs render
no comma"* rather than *"no template emits a localized number into a script"*. A template
added six days later was outside the assertion's reach and shipped green.

Separately, `editor_survey_layer_create` accepts a GeoJSON upload, validates it through
`validate_layer_upload`, creates the `SurveyMapLayer` row, and only then builds
`LayerObject`s. `LayerObject.geometry` is a 2D column, so a file carrying Z ordinates —
what QGIS and ArcGIS export by default — passes validation and dies at the database with
`DataError`. Two consequences, both confirmed in production:

- The creator gets an HTML 500 page where the JavaScript expects JSON, so the message
  they actually read is `Unexpected token '<', "<!DOCTYPE "… is not valid JSON`.
- The view is not atomic, so the already-created empty layer row survives. One such
  orphan is in production now (layer 87 on survey `edffa46f`, zero objects, 42 bytes —
  an empty FeatureCollection), and it counts against `MAX_LAYERS_PER_SURVEY = 10`.
  It is NOT hidden from its creator: the Reference layers card lists everything
  `layers_for()` returns with no `feature_count` filter, so the row shows as
  "New layer · 0 objects · 42 bytes" with a delete button. The cost is one of ten
  slots until they remove it, not a stuck record.

Production evidence that the retry loop is real: the layer that eventually succeeded on
survey `4a27c9ef` is named `br_hl___haltestellenkataster (3)` — a bus-stop cadastre,
uploaded on the third attempt, 189 objects.

## Goals / Non-Goals

**Goals:**

- The layer object editor works in every shipped creator language.
- The localization guard fails on a *new* template, not only on the two URLs someone
  thought to list in August.
- A 3D GeoJSON imports, dropping Z, instead of returning 500.
- A failed layer upload leaves no row behind and tells the creator what is wrong with
  their file in a sentence.
- Map position autosave either completes or is cancelled when its panel goes away —
  never throws, never silently discards a creator's move.

**Non-Goals:**

- Moving the inline map bootstrapping out of templates into `.js` modules. That would
  close this class permanently and is the right long-term shape, but it touches four
  templates' initialization order and is not a bug fix. Left as a follow-up.
- Storing Z. `LayerObject.geometry` stays 2D; nothing in the product reads elevation.
- Reprojecting. Z is discarded, X/Y are untouched.
- The other defects in the same PostHog sweep — `ProtectedError` on purge,
  `layerobject_unique_key_per_layer`, the `Http404` noise. Different subsystems.

## Decisions

### 1. The localization guard becomes a source scan, not a page render

**Decision.** Replace the two URL-pinned tests with one that walks every `.html` under
`survey/templates/`, extracts `<script>` bodies, and fails on a Django variable
interpolation that is not inside a `{% localize off %}` block and not passed through
`|unlocalize`.

**Why.** The repository already has this exact pattern and it already works:
`ExternalScriptCorsTest` (tests.py ~37025) walks the template tree rather than rendering
pages, and its docstring names the reason — *"the point is to fail when someone ADDS a
script tag, which no rendering test would cover."* `TemplateCommentSyntaxTest` does the
same for multi-line `{# #}`. This defect needs the same treatment for the same reason.

**Alternatives considered.**

- *Render every editor URL under a comma locale.* Rejected: it has the same blind spot
  we are fixing — a new page is unguarded until someone remembers to add its URL, which
  is precisely what happened in September.
- *Keep the URL tests and add the layer editor's URL.* Rejected: fixes the instance, not
  the class. This would be the third time.
- *A `settings.USE_L10N = False` flip.* Rejected: creator-visible readouts ("Lat: 52,52")
  should stay localized. The bug is only about numbers crossing into JavaScript.

**Trade-off.** A source scan is coarser than a render — it cannot tell a float from an
integer, so it will flag `{{ survey.start_map_zoom }}` too. That is acceptable and
arguably correct: a zoom is safe today only because it never exceeds 999.

### 2. Z is stripped during validation, not at the database boundary

**Decision.** `validate_layer_upload` normalizes coordinates to two ordinates as part of
the validation pass it already performs, so `objects_from_features` receives 2D features
and every caller inherits the fix.

**Why.** The view already has a working error contract — `LayerValidationError` → JSON
400 with a readable message — and the Z failure escapes it only because it surfaces after
validation, at `GEOSGeometry`/insert time. Closing the gap inside the existing contract
beats adding a second error path. It also covers the other two ingestion points for free:
`layers.py::objects_from_features` (bulk, also the ZIP import path) and
`layer_object_views.py` (single object).

**Alternatives considered.**

- *`ST_Force2D` in the database.* Rejected: the error is raised on insert, before any
  expression we control runs, and it would not help the ZIP import path.
- *Catch `DataError` in the view and translate it.* Rejected: it turns a fixable input
  into a permanent error message, and the creator still cannot import their file.
- *Reject 3D with a clear message.* Rejected: Z is the GIS default export, not a mistake.
  Discarding it is what every other tool does.

**Trade-off.** Silently dropping Z could surprise someone who believes elevation was
stored. The import report already lists what happened to the file; it gains a line when
Z was present.

### 3. The upload becomes atomic

**Decision.** Wrap the create-then-populate sequence in `transaction.atomic`.

**Why.** The orphan rows are not hypothetical — one is in production — and they consume a
cap of ten. This is one decorator and it makes every future failure in
`objects_from_features` clean up after itself, not only the Z case.

### 4. A missing element cancels the save; it does not guess a value

**Decision.** Give `MapPositionPicker` a `detach()` that clears the pending timer, call it
when the panel is torn down, and make `payload()` abandon the save when `extraFields()`
cannot produce a value — rather than substituting a default.

**Why.** The obvious fix is `el && el.checked ? '1' : '0'`, and that is wrong: with the
panel gone there is no element to read, so the "guard" would post `use_geolocation=0` —
a value the creator never chose — and persist it. A save that cannot be built correctly
must not be sent. The null guard stays as a second line of defence so a missed teardown
degrades to a skipped save rather than an exception, but the teardown is the fix.

**Alternatives considered.**

- *Null-guard only, at the three call sites.* Rejected for the reason above: it converts
  a visible exception into a silent wrong write, which is worse.
- *Read the checkbox eagerly at `attach()` time.* Rejected: its whole purpose is that the
  creator can toggle it, and `watch:` already re-saves on `change`.

## Risks / Trade-offs

- **The source scan flags existing legitimate interpolation** → Run it first and read the
  hits before writing the assertion; anything safe gets `{% localize off %}` too, which
  costs nothing. Pin the detector with a negative test, as the August work did.
- **`detach()` has no caller if the HTMX teardown hook is wrong** → The null guard makes
  that failure mode a skipped save instead of an exception; assert both halves separately
  so a silent no-op teardown still fails a test.
- **Local `master` is behind `origin/master`** → `#192` (`59ea01d`) introduced
  `map_position_picker.js` and `#193` (`fafd67d`) landed after. Branch from
  `origin/master`; editing the pre-`#192` templates in the local checkout would produce a
  diff against code that no longer exists. Note the remote moved twice during this
  change's analysis — re-fetch before branching.
- **Z-stripping changes stored geometry for re-imports** → It does not: existing rows are
  already 2D, because 3D ones could never be written. Nothing to migrate.
- **A test asserting "no localized decimal" can pass against broken code** → The August
  notes record three wrong versions that all passed: `translation.override` is discarded
  by `LocaleMiddleware`, `Accept-Language` loses to the language cookie, and `ru` is not
  in `LANGUAGES`. Set the cookie, and confirm each new test FAILS before the fix.

## Migration Plan

No migration. Ship in one PR; every piece is independently revertible at the file level.
Rollback is a revert — there is no data change and no kill switch to add.

Verification after deploy: the PostHog issues
`01a06dbf-…` (TypeError `'x'`) and the `Geometry has Z dimension` server issue should stop
receiving events. Both have a named, reachable reporter — `dominik.toennes@viakoeln.de`
hit all three defects — so a short note once it ships is warranted.

## Open Questions

- RESOLVED: leave orphan layer 87 to its creator. The Reference layers card already
  shows it with a delete button, so there is nothing for us to repair in someone else's
  survey; the atomicity fix stops new ones appearing.
- Does the import report surface the "Z discarded" line to the creator, or only to the
  logs? Leaning creator-visible, since they may be checking whether elevation survived.
