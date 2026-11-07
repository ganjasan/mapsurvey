## 1. Controls and preview (server)

- [x] 1.1 `survey/map_styles/controls.py`: `CONTROLS` (kinds: toggle, swatches+hex, preset, range, toggle), `ROAD_PRESETS`, `clean_settings(raw) -> (settings, errors)`, `settings_to_form(settings)` for the template
- [x] 1.2 `survey/map_styles/preview.py`: `for_maplibre(style, token)` (pure), `base_style()` with the public token cached a day (same cache key as the task), `maplibre_style(settings)`
- [x] 1.3 Views: `org_map_style_edit` (GET), `org_map_style_preview` (POST JSON), `org_map_style_save` (POST), URLs; gate roles + `require_feature('map_styles')` on save; 409 while pending; event `map_style_saved`
- [x] 1.4 Re-pin on live edits in `services.surveys.update_settings` and `services.sections.set_map`

## 2. Editor page (client)

- [x] 2.1 `org/map_style_editor.html` on `base.html`: name, controls rendered from `CONTROLS`, survey picker, Online / Print tabs, Save, status, "used in N surveys" note; MapLibre + CSS in `extra_head`
- [x] 2.2 `js/map_style_editor.js`: state from the JSON block, debounced preview POST → `map.setStyle(diff)`, unsaved marker, contrast warnings, pending poll, survey picker framing, greyscale toggle on the print image
- [x] 2.3 `css/map_style_editor.css`: two columns, stacks under 900 px; swatch grid; warning style
- [x] 2.4 Library cards: *Edit* link for workspace styles, Rename form removed, Duplicate + Edit on one line

## 3. Tests, docs, strings

- [x] 3.1 `survey/tests/test_map_style_editor.py`: every scenario of the new spec + the modified library scenario; allow-list the editor template/script in the `map-style-rendering` MapLibre scan; `UNMAPPED_MODULES` entry
- [x] 3.2 Help page section "Edit a style"; translations in the ten catalogs; PostHog event
- [x] 3.3 Full suite, `openspec validate --strict`
- [x] 3.4 Dev check on :8780: open editor, move a control, preview updates, Save → worker publishes → print tab shows the new version; screenshots for the owner
- [ ] 3.5 PR into `epic/map-styles`, merge, archive in a follow-up PR
