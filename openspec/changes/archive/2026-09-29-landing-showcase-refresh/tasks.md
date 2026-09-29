## 1. Screenshots

- [x] 1.1 Seed the demo locally, capture Build (layer editor), Collect (bridge card), Analyze (Responses map), Share (results page top) at 1920×1200
- [x] 1.2 Save `{build,collect,analyze,share}-full.webp` (1920×1200) and `{…}.webp` (1200×750)

## 2. Landing copy

- [x] 2.1 Showcase: four steps, new heading, copy and alt text
- [x] 2.2 Capabilities: six rewritten cards and icons, new heading; verify every claim (icon count, export formats, languages)

## 3. Overview map fix

- [x] 3.1 `editor_map.js` `hasSize` measures the container, not Leaflet's cached size
- [x] 3.2 Overview thumbnail: start view as map options, no `setView` after `mount()`

## 4. Verify

- [x] 4.1 Tests: landing shows four steps and six cards with existing images; guard tests for both map fixes
- [x] 4.2 Landing at 1366 px and 390 px; Overview thumbnail fitted on five consecutive loads; Map pane and drawer still draw
- [x] 4.3 Full test suite
