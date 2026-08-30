# Proposal: fix-editor-500s

## Why

Three unrelated defects, all surfaced by the PostHog error-tracking review of 2026-08-30, all
producing a 500 where the product should keep working. They ship together because each is small,
each is self-contained, and none needs the others.

**1. A section POST 500s when a controller question receives geometry** — 136 events, **62
respondents**, in 26 minutes on 2026-08-24 ([issue
`01a035f7`](https://eu.posthog.com/project/248938/error_tracking/01a035f7-0039-7ea0-9a75-d880e7a77c40)).
`survey/views.py` builds the submitted-state visibility map before storing anything:

```python
posted = [int(v) for v in request.POST.getlist(q.code) if v != '']
```

for every question whose `input_type` is a `CONTROLLER_TYPES` member (`choice`, `multichoice`).
The POST carried pipe-joined GeoJSON under such a question's code, so `int()` raised and the whole
submission died. This is the same class the storage branch below already guards against — its
comment says a stale type "routed a point question's GeoJSON into `int()` — an unhandled 500 on
every submit of the section" — but the visibility pre-pass was added later and never got the
lesson. Sixty-two people lost their answers.

**2. Structure export 500s for any survey with question images** — 9 events on 2026-08-29
([issue `01a04ddb`](https://eu.posthog.com/project/248938/error_tracking/01a04ddb-d466-71d2-8e5a-3fa69919e647)).
`collect_structure_images()` reads `question.image.path`; since media moved to S3 (2026-08-27) that
raises `NotImplementedError: This backend doesn't support absolute paths`. The trap is *named* in
the docstring of the neighbouring `collect_layer_files` — documented, not closed.

**3. Share and Settings pages have two dead buttons** — 1 event
([issue `01a02d79`](https://eu.posthog.com/project/248938/error_tracking/01a02d79-c502-7630-bcb4-9113c47e5fe8)).
`_survey_nav_tabs.html` wires Share and Preview to `onclick="navMenuToggle(...)"`, but that function
lives in `_lifecycle_scripts.html`, which `survey_share.html` and `survey_settings.html` never
include. Clicking either does nothing and throws `ReferenceError`. A Django test asserting the
button's markup passes — exactly the trap recorded in `lesson_test_client_misses_html5_validation`.

**This one is currently masked, not fixed.** Commit `928e927`, landed later the same day, wraps
those dropdowns in `{% if not MOBILE_EDITOR_NAV or active_tab == 'results' %}`, so with the flag at
its default (on) the buttons no longer render outside the Responses tab and the error stopped
appearing. Setting `MOBILE_EDITOR_NAV=False` is the documented rollback path, and on that path the
dead buttons are live again. The missing include is still a defect; it is simply invisible until
someone exercises the rollback.

## What Changes

- **The visibility pre-pass tolerates a non-integer value.** A controller question's posted values are
  parsed defensively; anything that is not an integer is ignored for visibility purposes rather than
  crashing the request. A question whose stored type and rendered widget disagree is a creator-side
  mistake; it must not cost a respondent their submission.
- **`collect_structure_images()` returns bytes, not filesystem paths.** Images are read through the
  storage API (`question.image.open()`), so the ZIP is written with `writestr` and the code works on
  both local disk and S3. The function's signature changes from `(archive_path, filesystem_path)` to
  `(archive_path, data)`; its single caller changes with it. A file the storage backend cannot open
  is skipped with an export warning instead of aborting the export.
- **`survey_share.html` and `survey_settings.html` include `_lifecycle_scripts.html`**, so the nav
  dropdowns work on every page that renders the nav.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `answer-persistence`: a section submission survives a posted value that does not match the
  question's stored type.
- `survey-serialization`: structure export reads images through the storage backend, so it works
  under remote storage.
- `survey-editor`: the survey nav's dropdown menus work on every page that renders the nav.

## Impact

- **Code**: `survey/views.py` (visibility pre-pass), `survey/serialization.py`
  (`collect_structure_images` + its caller), `survey/templates/editor/survey_share.html`,
  `survey/templates/editor/survey_settings.html`, tests in `survey/tests.py`.
- **No migrations, no settings, no URL changes.**
- **Export archives are byte-identical** for surveys whose images the backend can open; only the
  read path changes.
- **Memory cost**: structure images are held in memory while the ZIP is written rather than streamed
  from disk. Question images are small (creator-uploaded illustrations, not respondent uploads) and
  the export already builds `survey.json` in memory, so this does not change the profile
  meaningfully.
