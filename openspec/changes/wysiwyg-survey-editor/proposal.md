## Why

Surveys are currently created and edited exclusively through Django admin or JSON import — both require technical knowledge and provide no visual feedback. The "New Survey" and "Edit" buttons in the `/editor/` dashboard are non-functional stubs. A WYSIWYG editor lets non-technical users create, configure, and preview surveys visually, making the platform self-service.

## What Changes

- Add a visual survey editor at `/editor/surveys/<name>/` with a 3-column layout: sections sidebar, question editor, and live preview
- Add survey creation flow at `/editor/surveys/new/` replacing the non-functional "New Survey" button
- Add CRUD operations for sections: create, edit title/subheading/code, delete, drag-and-drop reorder (rebuilds linked list)
- Add CRUD operations for questions: create with type selector, edit all fields, delete, drag-and-drop reorder (updates order_number)
- Add visual choices editor for choice/multichoice/range/rating questions — dynamic add/remove rows with multilingual name support
- Add sub-question management for geo questions (point/line/polygon) — add/edit/delete sub-questions that appear in map popups
- Add section map position picker using Leaflet — click to set start_map_position and zoom
- Add translation management for sections and questions (inline forms per available language)
- Add survey settings editor (name, organization, languages, visibility, thanks_html)
- Add live inline preview via iframe that reloads on every edit, rendering the survey as respondents see it
- Wire the existing "Edit" link in the dashboard to the new editor
- Use HTMX for partial page updates and SortableJS for drag-and-drop — no SPA framework, no build step

## Capabilities

### New Capabilities
- `survey-editor`: Core WYSIWYG editor interface — 3-column layout, section/question CRUD, drag-and-drop reorder, choices editor, sub-question management, map position picker, translation forms, survey settings, and live preview

### Modified Capabilities
- `survey-serialization`: The editor creates surveys directly via ORM, but the serialization format documents the data structures the editor must produce. No spec-level requirement change — just implementation overlap.

## Impact

- **New files**: `survey/editor_views.py`, `survey/editor_forms.py`, ~12 templates in `survey/templates/editor/`
- **Modified files**: `survey/urls.py` (new editor URL patterns), `survey/templates/editor.html` (wire "New Survey" and "Edit" links)
- **New frontend dependencies**: HTMX (~14KB CDN), SortableJS (~10KB CDN) — loaded only on editor pages
- **Existing dependencies**: Leaflet (already loaded) reused for map position picker
- **Models**: No schema changes — editor operates on existing SurveyHeader, SurveySection, Question, and translation models
- **Auth**: All editor views require `@login_required`
