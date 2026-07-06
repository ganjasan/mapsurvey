# Tasks — thanks-page-editor

## 1. Branding: make mandatory, keep the flag

- [x] 1.1 `_made_with_mapsurvey.html`: drop the `{% if survey.show_branding %}`
      guard so the CTA always renders (survey/thanks/results)
- [x] 1.2 Remove `show_branding` from `SurveyHeaderForm.Meta.fields` (keep the
      model field); confirm no settings-panel autosave path posts it anymore
- [x] 1.3 Audit tests that toggle/assert `show_branding` hiding the CTA; update to
      the mandatory behavior (flag retained in serialization/versioning)

## 2. Thanks editor — backend

- [x] 2.1 Add `nh3` to `Pipfile` (project uses pipenv, not requirements.txt);
      `sanitize_thanks_html(html)` in `views.py` (allow-list: `h1-h4,p,br,strong,
      b,em,i,u,s,a,ul,ol,li,blockquote,span,div`; `a`→`href,title,target`; nh3
      `link_rel='noopener noreferrer'` manages rel). NOTE: `Pipfile.lock` must be
      regenerated (`pipenv lock`) before deploy — pipenv was broken in this env,
      so the lock still needs `nh3`; the local venv has it (`pip install nh3`).
- [x] 2.2 `editor_survey_thanks_panel(request, survey_uuid)` view: GET renders the
      editor partial; POST saves the per-language HTML into `thanks_html` (sanitized)
      and returns JSON for XHR autosave / redirect for plain submit (mirror
      `editor_survey_settings_panel`)
- [x] 2.3 URL `editor/surveys/<uuid>/thanks-panel/` → `editor_survey_thanks_panel`
- [x] 2.4 `editor_survey_detail`: accept `?panel=thanks` → initial center panel is
      the thanks editor (like `panel=settings`)

## 3. Thanks editor — frontend

- [x] 3.1 `editor/partials/thanks_panel.html`: `.pr-ctxbar` ("Thanks page / The last
      screen respondents see"), a Quill (CDN) editor card with per-language tabs
      (only when >1 language), hidden inputs holding each language's HTML, and a
      live preview card showing rendered HTML + fixed share button + mandatory
      branding footer; debounced autosave with a status indicator
- [x] 3.2 Pinned "Thanks page" sidebar entry at the bottom of `survey_detail.html`
      (below `section-list`/"New Section"), `?panel=thanks`; JS click handler swaps
      it into `#section-content` and manages active state (mirror settings panel)
- [x] 3.3 Remove the "Thanks page" card from `survey_settings_panel.html`
- [x] 3.4 Load Quill CSS/JS (CDN) where the thanks panel needs it
- [x] 3.5 Show the thanks page in the Build live-preview pane: editor-only
      `editor_survey_thanks_preview` view + `thanks-preview/` URL (renders
      `survey_thanks.html` in the requested lang, no session side effects, gated
      on editor access so drafts/private preview too — the public `survey_thanks`
      view is left untouched); the preview iframe always renders and points at the
      thanks preview when the thanks panel is active; opening the thanks pinned
      entry repoints the iframe, and the panel's autosave refreshes it via
      `window.refreshBuildPreview`

## 4. Verification

- [x] 4.1 Tests: thanks-panel GET returns the editor; POST sanitizes and stores
      per-language `thanks_html`; disallowed tags/attrs stripped; XHR→JSON,
      plain→redirect
- [x] 4.2 Tests: `?panel=thanks` renders with the thanks editor as initial content;
      settings panel no longer contains a thanks field
- [x] 4.3 Tests: branding CTA renders on survey/thanks pages regardless of
      `show_branding`; `show_branding` still round-trips serialization/versioning
- [x] 4.4 Full `./run_tests.sh survey` green
- [x] 4.5 Manual: edit thanks content (bold/heading/link/list), switch language,
      confirm autosave + public thanks page matches the preview incl. branding
