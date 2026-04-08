## Context

The analytics dashboard (analytics_dashboard.html) has a flat split model: `_pinnedPanel` moves one panel DOM element to `#data-secondary`, single tab bar controls `#data-primary`. State: `_activeDataPanel` + `_pinnedPanel`. Resize is X-axis only (col-resize). Panels use live widgets (Leaflet map, Chart.js, HTMX table) — must be moved, never cloned.

## Goals / Non-Goals

**Goals:**
- Recursive split tree (leaf = pane, split = direction + two children + sizes)
- Each pane has own tab bar + split/close controls
- Split right and split down from any pane
- Up to N panes (limited by number of panel types)
- Panel swap when selecting a panel already in another pane
- Resize dividers on both axes
- Persist full tree to localStorage with old format migration

**Non-Goals:**
- Drag & drop tabs between panes
- Same panel in multiple panes (panels are unique DOM elements)
- External JS files — everything stays inline in the template

## Decisions

### 1. Tree data model

**Choice**: JS object tree with `{ type: 'leaf', id, panel }` and `{ type: 'split', id, direction, children: [node, node], sizes: [50, 50] }`.

**Why**: Natural recursive structure. Easy to serialize for localStorage. Tree operations (find, replace, parent lookup) are simple recursive functions. Sizes stored as percentages on the split node.

### 2. Full re-render on tree change

**Choice**: `_renderTree()` detaches panel DOM elements to a hidden `#panel-pool`, clears the container, builds new DOM from tree, moves panels back into their leaf content divs.

**Why**: Incremental DOM updates for tree restructuring (split/close) are complex and error-prone. Panel DOM elements preserve state when moved (Canvas content, Leaflet L.Map instances, HTMX state). Only need `map.invalidateSize()` and `window.resize` dispatch after render. Simpler code, same result.

### 3. Per-pane controls layout

**Choice**: Each leaf pane has a compact header bar:
```
[Table] [Map] [Charts]          [⊞→] [⊞↓] [✕]
```
Tabs on the left, split-right / split-down / close buttons on the right. Close hidden when only one pane exists. Split buttons disabled (grayed) when all panels are in use.

**Why**: Matches VS Code's editor group header pattern. No global split button needed — actions are contextual to each pane.

### 4. Panel swap on tab click

**Choice**: When user clicks a tab for panel X in pane A, and panel X is already shown in pane B, swap A's panel into B and X into A.

**Why**: Panels can't be duplicated. Swap is the least surprising behavior — both panes stay populated. Alternative (close the other pane) would be destructive.

### 5. Global toolbar simplification

**Choice**: Remove the old Split/Unsplit buttons from the global toolbar. Split/close controls live on each pane. The global toolbar only shows the hidden-indicator.

**Why**: With per-pane controls, global split button is redundant. Cleaner UI.

## Architecture

### State

```
var _splitTree = { type: 'leaf', id: 'pane-0', panel: 'table' };
var _nextPaneId = 1;
var _nextSplitId = 1;
var _PANELS = [
    { id: 'table', label: 'Table', icon: 'fa-table' },
    { id: 'map', label: 'Map', icon: 'fa-map' },
    { id: 'charts', label: 'Charts', icon: 'fa-chart-bar' },
];
```

### Tree helper functions

- `_findNode(tree, id)` — recursive search by id
- `_replaceNode(tree, id, replacement)` — returns new tree with node replaced
- `_removeLeaf(tree, leafId)` — removes leaf, collapses parent split
- `_allLeaves(tree)` — returns flat array of leaf nodes
- `_usedPanels(tree)` — returns Set of panel ids currently in leaves

### Core actions

- `splitPane(paneId, direction)` — creates new split with old leaf + new leaf
- `closePane(paneId)` — removes leaf, collapses parent
- `setPanePanel(paneId, panelId)` — swap if in another pane, else switch
- `startSplitResize(splitId, event)` — drag handler, branches on direction

### DOM rendering

- `_renderTree()` — entry point: detach panels → clear container → build → reattach → post-render
- `_buildNode(node)` — dispatches to leaf or split builder
- `_buildLeaf(node)` — creates wrapper with tab bar + content, moves panel DOM element in
- `_buildSplit(node)` — creates flex container + divider + recursive children
- `_postRender()` — invalidateSize on map, dispatch resize for charts

### CSS additions

```css
.split-pane-leaf { display: flex; flex-direction: column; overflow: hidden; }
.split-pane-tabbar { display: flex; align-items: center; background: #f8f9fa;
    border-bottom: 1px solid var(--border-color); padding: 0 0.5rem; flex-shrink: 0; min-height: 30px; }
.split-pane-tab { padding: 0.2rem 0.7rem; border: none; background: none;
    border-bottom: 2px solid transparent; cursor: pointer; font-size: 0.78rem; color: #6b7280; }
.split-pane-tab.active { border-bottom-color: var(--accent); font-weight: 600; color: var(--accent); }
.split-pane-tab:hover { color: var(--accent); }
.split-pane-actions { margin-left: auto; display: flex; gap: 2px; }
.split-pane-actions button { border: none; background: none; cursor: pointer;
    color: #9ca3af; font-size: 0.7rem; padding: 2px 5px; border-radius: 3px; }
.split-pane-actions button:hover { background: #e5e7eb; color: #374151; }
.split-pane-actions button:disabled { opacity: 0.3; cursor: default; }
.split-pane-content { flex: 1; min-height: 0; overflow: hidden; position: relative; }
.split-pane-content > .data-panel { flex: 1; min-height: 0; overflow: auto; }
.split-divider { background: #e5e7eb; flex-shrink: 0; border-radius: 3px; }
.split-divider:hover { background: #d1d5db; }
```

### localStorage schema

```json
{
  "version": 2,
  "tree": { "type": "split", "direction": "horizontal", ... }
}
```

Migration: if no `version` field, read old `activePanel`, build single-leaf tree.
