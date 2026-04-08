## 1. Remove old split infrastructure

- [ ] 1.1 Remove old state vars: `_activeDataPanel`, `_pinnedPanel`
- [ ] 1.2 Remove old functions: `pinCurrentPanel()`, `unpinPanel()`, `switchDataPanel()`, old `startSplitResize()`
- [ ] 1.3 Remove old global toolbar split/unsplit buttons (`#pin-panel-btn`, `#unpin-panel-btn`)
- [ ] 1.4 Remove old static `#data-split-divider` and `#data-secondary` elements
- [ ] 1.5 Remove old tab bar buttons (`.data-panel-tab`) from global toolbar

## 2. Add tree state and helpers

- [ ] 2.1 Add `_splitTree`, `_nextPaneId`, `_nextSplitId`, `_PANELS` state vars
- [ ] 2.2 Implement `_findNode(tree, id)` — recursive search
- [ ] 2.3 Implement `_replaceNode(tree, id, replacement)` — returns new tree
- [ ] 2.4 Implement `_removeLeaf(tree, leafId)` — removes leaf, collapses parent split to remaining child
- [ ] 2.5 Implement `_allLeaves(tree)` — flat array of leaves
- [ ] 2.6 Implement `_usedPanels(tree)` — Set of panel ids in use

## 3. Add DOM rendering

- [ ] 3.1 Add hidden `#panel-pool` div to hold detached panel elements
- [ ] 3.2 Implement `_buildLeaf(node)` — creates `.split-pane-leaf` wrapper with tab bar (tabs + split/close buttons) and `.split-pane-content` div, moves panel DOM element in, calls `_showPanel`
- [ ] 3.3 Implement `_buildSplit(node)` — creates flex container (direction from node), builds children recursively, adds `.split-divider` between them with appropriate cursor and `onmousedown`
- [ ] 3.4 Implement `_buildNode(node)` — dispatches to `_buildLeaf` or `_buildSplit`
- [ ] 3.5 Implement `_renderTree()` — detach all panels to `#panel-pool`, clear `#data-split-container`, build tree DOM, append to container, call `_postRender()`
- [ ] 3.6 Implement `_postRender()` — `map.invalidateSize()` with setTimeout(150), dispatch `window.resize` for Chart.js, handle `_tableLoaded` guard

## 4. Add core actions

- [ ] 4.1 Implement `splitPane(paneId, direction)` — find leaf, compute available panel, create new split node wrapping old leaf + new leaf, replace in tree, `_renderTree()`, `_saveLayout()`
- [ ] 4.2 Implement `closePane(paneId)` — find leaf, if tree is single leaf return (no-op), remove leaf from tree (collapse parent split), `_renderTree()`, `_saveLayout()`
- [ ] 4.3 Implement `setPanePanel(paneId, panelId)` — if panelId is in another pane, swap both panels; else just assign. `_renderTree()`, `_saveLayout()`
- [ ] 4.4 Implement `startSplitResize(splitId, event)` — read direction from split node, use clientX/offsetWidth for horizontal, clientY/offsetHeight for vertical, clamp 200px min, update `sizes[]`, apply flex percentages, `_saveLayout()` on mouseup

## 5. Update HTML structure

- [ ] 5.1 Restructure `#data-primary`: remove inner tab bar, wrap panel elements in `#data-primary-content` (or let `_renderTree` manage it entirely — panels start in `#panel-pool`)
- [ ] 5.2 Keep `#data-split-container` as the tree root mount point
- [ ] 5.3 Keep hidden-indicator outside the split container (global, not per-pane)
- [ ] 5.4 Remove old `.data-panel-tab` buttons from outer toolbar

## 6. Add CSS

- [ ] 6.1 Add `.split-pane-leaf`, `.split-pane-tabbar`, `.split-pane-tab`, `.split-pane-actions` styles
- [ ] 6.2 Add `.split-pane-content > .data-panel` flex fill rules
- [ ] 6.3 Add `.split-divider` styles (horizontal: width 6px, vertical: height 6px)
- [ ] 6.4 Update fullscreen CSS selectors from `#data-primary > .data-panel` to `.split-pane-content > .data-panel`
- [ ] 6.5 Preserve `#data-panel-map` special flex/overflow rules

## 7. Update persistence

- [ ] 7.1 Replace `_saveDataLayout()` → `_saveLayout()` — serialize `{ version: 2, tree: _splitTree }`
- [ ] 7.2 Replace `_restoreDataLayout()` → `_restoreLayout()` — parse tree, migrate old format (no version field → single leaf from `activePanel`)
- [ ] 7.3 Update `DOMContentLoaded`: call `_restoreLayout()` then `_renderTree()` instead of old `switchDataPanel()`

## 8. Integration fixes

- [ ] 8.1 Update `switchAnalyticsTab('data')` — instead of calling `switchDataPanel`, call `_renderTree()` if tree not yet rendered
- [ ] 8.2 Verify `FilterManager._renderSelection()` works with panels in arbitrary pane locations (it queries by panel element ID, should be fine)
- [ ] 8.3 Verify anomalies sidebar still works inside `#data-panel-table` when moved between panes
- [ ] 8.4 Verify fullscreen (`togglePanelFullscreen`) works on panels inside split panes
- [ ] 8.5 Verify map `invalidateSize` is called after every tree render where map is visible
