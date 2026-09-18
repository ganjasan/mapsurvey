## 1. Reproduce before fixing

- [x] 1.1 Write a failing test: a trashed survey with a reference layer and a `layer_objects` question bound to it; `purge_survey()` raises `ProtectedError` today
- [x] 1.2 Confirm the test fails for the RIGHT reason — read the exception and see `Question.layer`, not a fixture mistake

## 2. Purge the layers

- [x] 2.1 In `purge_survey()`, clear `Question.layer` for questions inside the header family before the layers go (`update(layer=None)`, scoped through `survey_section__survey_header__in=headers` — never through the layer)
- [x] 2.2 Delete `SurveyMapLayer.objects.filter(survey__in=headers)` explicitly, next to the existing session deletion, with a comment naming the PROTECT the way the session line does
- [x] 2.3 Delete `LayerObjectAsset` files through the storage API in the media-cleanup block, before the rows go
- [x] 2.4 Test: purge removes survey, question, layer and objects; nothing raises
- [x] 2.5 Test: a survey with a live draft copy whose question borrows the canonical's layer purges completely
- [x] 2.6 Test: a question in an unrelated survey keeps its `layer_id` after the purge

## 3. Auto-purge keeps going

- [x] 3.1 Isolate the per-survey call in `purge_expired_surveys()`; log the survey and the exception, count it, continue
- [x] 3.2 Return failures alongside the purged count, and surface them in the `/internal/purge-trash/` response and the management command's output
- [x] 3.3 Test: three expired surveys, the middle one raising — the other two are purged and the result reports one failure
- [x] 3.4 Check the callers: `purge_trashed_surveys` command and the internal endpoint both read the new return shape

## 4. Tell the creator what goes with it

- [x] 4.1 Count layers and objects per trashed survey where the trash list is built — one aggregate for the owner's list, not a query per row
- [x] 4.2 Add the line to the Delete-forever modal in `editor.html`; wire it through the existing `data-survey-*` attributes the modal already reads
- [x] 4.3 Translate the new string into the ten UI catalogs
- [x] 4.4 Test: the dialog names the counts for a survey with layers, and is byte-identical to today for one without

## 5. Verify and ship

- [x] 5.1 `./run_tests.sh survey -v2` — one baseline before the work, one after; summarize the delta, do not iterate on the runner
- [x] 5.2 Drive it in a browser: trash a survey with a layer, read the dialog, press Delete forever, confirm it disappears
- [x] 5.3 `openspec validate purge-survey-with-layers --strict`
- [ ] 5.4 Open the PR against `master`; no migration and no kill switch, so rollback is a revert
- [ ] 5.5 After deploy: re-run the production count of trashed surveys owning layers (9 as of 2026-09-18) and confirm the nine Delete-forever buttons work
- [ ] 5.6 Resolve PostHog issue `01a0a513-…` once no new events arrive
- [ ] 5.7 Write to the creator who hit it ten times — thank and "fixed", no cause detail
