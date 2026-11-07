## Why

The owner asked how a creator makes a new style: today only by guessing that *Duplicate* on a preset is the way in, after which they land back on the library and have to find *Edit*. A creator who came to make their own map should see a **New style** button and end up in the editor. Two leftovers from the epic's screenshots go with it: the library's subtitle still says the editor is coming, and the photocopy warning fires on Paper A's own park colour.

## What Changes

- **New style** (primary button in the library header) with a small menu of the presets to start from — Streets, Paper A, Paper B, each with its preview tile. Choosing one creates a workspace style named "New style" (suffixed when taken), publishes it in the background and opens it **in the editor**.
- **Duplicate** also opens the new style in the editor instead of returning to the library.
- The library subtitle describes the editor that exists.
- Contrast warning threshold 0.12 → 0.08: Paper A's parks (`#dcefd2`, 0.087 from white) no longer warn; really pale colours still do.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `map-style-library`: *New style* added; *Duplicate* lands in the editor.
- `map-style-editor`: contrast threshold 0.08.

## Impact

`survey/map_style_views.py` (shared `_create_from`, `org_map_style_new`), `survey/urls.py`, `org/map_styles.html`, `js/map_style_editor.js`, tests, help page, locales. No model change.
