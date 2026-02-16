## Context

The survey versioning system archives old survey structures when a new version is published. The `download_data` view already supports `?version=latest|vN|all` query parameter, but there is no UI to access it. The "Download Data" link in `editor.html` always points to `/surveys/<uuid>/download` (latest only).

Surveys expose `get_version_history()` which returns archived versions ordered by `-version_number`. Each archived version has a `version_number` field.

## Goals / Non-Goals

**Goals:**
- Allow users to choose which version's data to download from the editor dashboard
- Keep the UI simple — a dropdown next to the existing download link

**Non-Goals:**
- Changing the backend download API (already complete)
- Adding version selection to the public survey URL
- Version comparison or diff UI

## Decisions

### 1. Dropdown-style download menu (like Export)

Replace the plain "Download Data" link with a dropdown that shows version options. This is consistent with the existing "Export" dropdown pattern already in `editor.html`.

For surveys with only v1 (no history), show the plain link as before — no dropdown needed.

For surveys with history (v2+), show:
- "All Versions" → `?version=all`
- "Current (vN)" → `?version=latest`
- "v1", "v2", etc. → `?version=vN`

### 2. Template-only approach with annotated queryset

Pass version history info via the template context by annotating each survey in the dashboard view with its version history. No new endpoint needed — the `editor` view already queries surveys and can prefetch archived versions.

Alternative considered: AJAX endpoint to load versions on click. Rejected — unnecessary complexity for a small number of versions.

## Risks / Trade-offs

- [N+1 queries] → Use `Prefetch` on `get_version_history()` relationship to batch-load archived versions for all surveys in one query.
- [Dropdown clutter for many versions] → Acceptable for now — surveys rarely exceed 5-10 versions.
