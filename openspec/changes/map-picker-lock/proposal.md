## Why

The survey's default map position is the centre of a map that sits inline on the settings page and in the
in-editor settings panel, and every settled move of that map is saved at once (change
map-picker-centre-autosave). A creator who only scrolls through the settings moves it without meaning to:
the wheel or trackpad zooms the map the moment the cursor passes over it, a finger that starts a page
scroll on the map drags it. The move is saved silently, and a carefully framed start position is gone.
Creators report losing the position this way often.

## What Changes

- The settings-page and settings-panel position maps open **locked**: drag, wheel, pinch, double-click,
  box and keyboard movement are off, so scrolling over the map scrolls the page. A "Change position"
  button on the map unlocks it.
- Unlocked, the map behaves as before (centre is the position, every settled move autosaves) and shows a
  "Done" button. It locks again on "Done", on a click or tap anywhere outside the map, and when the map
  scrolls out of view.
- Place search and the geolocation switch keep working while locked: choosing a search result is a
  deliberate act and moves (and saves) the position without unlocking.
- The section map picker (a modal opened for that purpose) is unchanged.

## Capabilities

### Modified Capabilities

- `survey-editor`: the survey default map position picker is locked until the creator asks to move it.

## Impact

- `survey/assets/js/map_position_picker.js` — `lock` option, `lock()` / `unlock()`.
- `survey/templates/editor/survey_settings.html`, `editor/partials/survey_settings_panel.html` — pass
  `lock: true` and two labels; `editor_base.html` — styles of the lock controls.
- One new creator string ("Change position") in every catalog; "Done" exists.
- Tests in `survey/tests/test_survey_editor.py`; changelog entry; `.claude/architecture/creator-ui.md`.
- No migration, no endpoint change.
