## Why

The analytics dashboard split view currently supports only "pin one panel to the right" — a flat two-pane model. Users can't see all three panels (Table, Map, Charts) simultaneously, and there's no split-down option. VS Code's editor groups use a recursive split tree that allows arbitrary layouts (split right, split down, nested). This is the expected UX for a data analysis workspace.

## What Changes

- **Recursive split tree model**: Replace flat `_pinnedPanel` / `_activeDataPanel` with a tree data structure. Leaf = pane showing one panel. Split = two children in a direction (horizontal/vertical) with resizable sizes.
- **Per-pane tab bar**: Each leaf pane has its own Table/Map/Charts tabs + Split Right / Split Down / Close buttons.
- **Split any pane**: Any pane can be split right or down, creating a nested split. New pane gets the first unused panel.
- **Close any pane**: Close button removes a leaf; parent split collapses to the remaining child.
- **Panel swap**: Selecting a panel already shown in another pane swaps both.
- **Split dropdown replaced**: Single "Split" button replaced by per-pane split controls.
- **Resize both axes**: Dividers adapt cursor and axis based on split direction.

## Capabilities

### New Capabilities

- `split-down`: Panes can be stacked vertically (not just side-by-side).
- `multi-pane`: Up to N panes (one per panel type) in any nested layout.
- `per-pane-tabs`: Each pane independently selects which panel to show.
- `direction-toggle`: Each split's direction is set at creation time.

### Modified Capabilities

- `split-resize`: Resize now works on both X and Y axes depending on split direction.
- `layout-persistence`: localStorage stores the full tree (with migration from old flat format).

## Impact

- **Modified files** (all client-side, no server changes):
  - `survey/templates/editor/analytics_dashboard.html` — HTML structure, CSS, and all split JS logic
- **No backend changes**
- **Backward compatible**: Old localStorage format migrated automatically
