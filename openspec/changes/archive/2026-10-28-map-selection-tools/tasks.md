## 1. Backend

- [x] 1.1 Add `SurveySession` to imports in `analytics_views.py`
- [x] 1.2 Implement `analytics_session_detail` view
- [x] 1.3 Add URL pattern for `analytics_session_detail` in `urls.py`

## 2. Session Detail Template

- [x] 2.1 Create `analytics_session_detail.html` with session metadata header
- [x] 2.2 Add answer table (section / question / value)
- [x] 2.3 Add conditional mini-map with lazy init and cleanup

## 3. Dashboard Extensions

- [x] 3.1 Add Leaflet.draw CSS + JS to `analytics_dashboard.html` extra_head
- [x] 3.2 Add `toggleGeoSid()` method to FilterManager
- [x] 3.3 Add toolbar CSS (`.geo-toolbar`, `.geo-toolbar-btn`)

## 4. Geo Map Toolbar and Tools

- [x] 4.1 Create L.Draw.Rectangle and L.Draw.Polygon handler instances
- [x] 4.2 Implement `window.setGeoTool(name)` function
- [x] 4.3 Replace feature click handler with mode-aware version (pointer/details)
- [x] 4.4 Add Ctrl+click guard for multi-select in pointer mode
- [x] 4.5 Add geoToolMode guard to map click deselect handler
- [x] 4.6 Add `draw:created` event handler with bounds/polygon intersection
- [x] 4.7 Implement `openSessionDetailModal(sid)` function
- [x] 4.8 Add ToolbarControl L.Control at topright
- [x] 4.9 Add modal shell HTML to template

## 5. Tests

- [x] 5.1 Test `analytics_session_detail` returns 200 with answer data
- [x] 5.2 Test `analytics_session_detail` returns 404 for wrong survey
- [x] 5.3 Test `analytics_session_detail` requires auth
