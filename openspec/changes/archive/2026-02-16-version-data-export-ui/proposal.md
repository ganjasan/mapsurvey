## Why

The backend supports version-aware data export via `?version=latest|vN|all` query parameter, but there is no UI to access this. Users cannot download data from previous survey versions without manually constructing URLs.

## What Changes

- Add a version selector to the data download flow in the editor dashboard
- When a survey has multiple versions, show a dropdown/modal allowing the user to choose which version(s) to download
- For surveys with only one version, keep the existing simple download link

## Capabilities

### New Capabilities
- `version-export-ui`: UI component in the editor dashboard for selecting survey version when downloading response data

### Modified Capabilities
_None_ — the backend API (`?version=`) is already implemented. This change is purely frontend/template.

## Impact

- **Templates**: `editor.html` — modify the download link/button to include version selection
- **Views**: May need a lightweight endpoint to return available versions for a survey (or pass version info via template context)
- **No model changes**: All versioning fields and logic already exist
