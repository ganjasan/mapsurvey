# Tasks — skip-and-create-empty

## 1. Implementation

- [x] 1.1 `editor_survey_create`: read the action once; treat `empty_skip` as a manual
      creation that applies neither `map_lat/lng/zoom` nor `default_basemap`, leaving the
      model defaults. `empty` / no action keep today's behaviour verbatim
- [x] 1.2 `survey_create.html`: rename the AI-branch button to
      "Skip and Create Empty Survey" and post `action=empty_skip`; the no-AI branch keeps
      "Create Survey" / `action=empty`
- [x] 1.3 Confirmation script: on click, if `goal`/`audience`/`map_target` hold
      non-whitespace text, `Dialog.confirm` naming the loss and submit only on confirm;
      the use-case chip is excluded because it is preselected. The script is rendered
      only under `ai_available` — without the panel there is no brief to confirm away

## 2. Tests

- [x] 2.1 `action=empty_skip` with map fields posted → survey has default start position,
      zoom and base map, and redirects to its editor
- [x] 2.2 `action=empty` with the same POST → map position, zoom and base map still stored
      (regression on the untouched contract)
- [x] 2.3 Rendered page: the AI branch carries the "Skip and Create Empty Survey" label and
      `value="empty_skip"`; the no-AI branch carries `value="empty"`

## 3. Verify

- [x] 3.1 Run the survey suite (offset 20 collides with the wizard-create-btn worktree;
      ran against a throwaway stack on 5594/6539)
- [x] 3.2 Drive the real page in a browser (Playwright, local stand with a fake Gemini
      key so the panel renders): blank brief → straight to the editor, no dialog; typed
      goal → dialog "Create an empty survey?"; Cancel keeps the page and the typed text;
      OK lands in the editor. Both created surveys have `start_map_postion`,
      `start_map_zoom` and `default_basemap` NULL despite the picker posting values
