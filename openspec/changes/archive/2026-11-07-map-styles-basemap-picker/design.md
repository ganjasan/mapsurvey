## Decisions

- **Inline fold, not a floating dropdown.** The panel is long and autosaves; a fold that pushes
  content down has no z-index or outside-click issues and works the same on a phone.
- **The hidden `basemaps` input stays the value carrier.** Checkboxes have no `name`; the panel's
  autosave already reads the hidden input on every bubbling `change`.
- **Default filtering in the browser.** `clean()` already moves a default that is not enabled to the
  first base map; the select now shows the same rule before saving. When it moves the default it
  fires a non-bubbling `change` so the position map follows without a second autosave.
- **The filter input stops its events.** Typing a search is not a settings change.
- **Position map uses `{% basemap_table org %}` without pins**: a creator surface shows newest
  versions, like the editor preview.
