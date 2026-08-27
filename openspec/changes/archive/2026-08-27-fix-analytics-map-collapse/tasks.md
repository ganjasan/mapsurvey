# Tasks: fix-analytics-map-collapse

## 1. Fix

- [x] 1.1 `switchAnalyticsTab`: restore `display:'flex'` for `#pane-data` instead of `''`
- [x] 1.2 Guarded fullscreen helpers (`_enterFullscreen`/`_exitFullscreen`/`_fullscreenElement`) used by both toggles

## 2. Verification

- [x] 2.1 Playwright mobile (<768px): Map pane at load has non-zero map height, tiles render
- [x] 2.2 Playwright desktop: Data → Performance → Data keeps map height; no console TypeError when fullscreen API is absent
- [x] 2.3 Template guard test
