## Decisions

### D1. One creation path
`_create_from(request, org, source, name, surface)` is Duplicate's old body: trial use, style + pending version 1 with the source's settings, publish on commit, event `map_style_created` (now with `surface`: `new` | `duplicate`), redirect to the editor. *New style* and *Duplicate* both call it, so the gate, the trial count and publishing cannot drift.

### D2. Start from a preset, not from nothing
A blank style has no meaning for the generator (it edits `streets-v12`); a creator picks the look closest to what they want. The menu lists the presets the generator can rebuild (Streets, Paper A, Paper B) with their preview tiles; Satellite and Topo are absent as they are from *Duplicate*.

### D3. Land in the editor while publishing
The editor works on a pending version: the controls show its settings, the preview renders them in the browser, Save is disabled until the first version is published (seconds). Nothing else to change.

### D4. Threshold
0.08 on the greyscale luminance difference: `#dcefd2` (Paper A parks) on white is 0.087, `#f4f9f0` is 0.03.
