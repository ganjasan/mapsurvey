## 1. Shared assets

- [x] 1.1 Write `survey/assets/css/loading-feedback.css`: fixed 3 px top bar (`.ms-progress`), accent colour, z-index 2000, width/opacity transitions, `prefers-reduced-motion` rule, `.is-busy` button rule.
- [x] 1.2 Write `survey/assets/js/loading_feedback.js`: bar element created on first use; counted `start(delay)`/`done()` with trickle; `busy(button)`/release swapping the leading icon; `reset()`; `window.LoadingFeedback` export.
- [x] 1.3 Navigation hooks in the script: `window` bubble listeners for `click` (link filter per design D3) and `submit` (D4: submitter busy on next tick, `data-ms-submitting` re-submit suppression, `data-no-progress` and `target` exclusions), `pageshow`/`persisted` reset, 30 s watchdog.
- [x] 1.4 HTMX hooks in the script: `htmx:beforeSend` → start(300) + busy submitter, `htmx:afterRequest` → done + release, paired on `detail.xhr`; skip `hx-trigger` containing `every`; 60 s safety release.
- [x] 1.5 Create `survey/templates/partials/_loading_feedback.html` (stylesheet link + script tag with the debug cache-buster the bases use).

## 2. Wiring

- [x] 2.1 Include the partial in the `<head>` of `survey/templates/base.html` and `survey/templates/editor/editor_base.html`.
- [x] 2.2 Add `survey/changelog/2026-10-15-visible-loading-bar.html` (`kind: new`).

## 3. Tests

- [x] 3.1 `LoadingFeedbackTest` (SimpleTestCase) in `survey/tests.py`: both creator bases include the partial once; `base_survey_template.html` and `base_landing.html` do not; the static files exist; the script pairs `htmx:beforeSend` with `htmx:afterRequest`, resets on `pageshow`, disables busy buttons only inside a `setTimeout`, gives GET buttons no busy state, and skips `every` triggers.
- [x] 3.2 Run `./run_tests.sh survey.tests.LoadingFeedbackTest survey.tests.ChangelogEntriesTest survey.tests.HtmxPromiseGuardTest survey.tests.TemplateCommentSyntaxTest` and the full `survey` suite once.

## 4. Verification in the browser

- [x] 4.1 `collectstatic`, start the dev server on this worktree's ports, sign in; throttle the network and confirm the bar on a tab navigation, no bar on a fast one, busy state on a native submit (settings) and an HTMX submit (question modal Save), reset after Back.
- [x] 4.2 Confirm the import-jobs poll shows no bar and the section form autosave still saves.

## 5. Found during verification

- [x] 5.1 Synchronous `disabled` on an `hx-get` + `data-toggle="modal"` button stopped Bootstrap's delegated click (the Edit modal never opened): disable every busy button on the next tick, busy state only for non-GET HTMX buttons; spec, design D4/D5 and the test updated.
- [x] 5.2 Changelog id `2026-10-15-loading-bar` sorted before today's `publish-keeps-rules`, so the watermark would have hidden the card: renamed to `2026-10-15-visible-loading-bar`.
- [x] 5.3 Out of scope, reported separately: on master, Enter in the new-question Name field before a type is picked creates two questions (the htmx submit, then the modal's save-on-close draft POST).
