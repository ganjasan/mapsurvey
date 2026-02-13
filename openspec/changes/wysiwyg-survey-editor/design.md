## Context

Surveys are managed through Django admin or JSON import. The `/editor/` dashboard lists surveys with export/import/delete actions, but "New Survey" and "Edit" buttons are non-functional stubs. The codebase uses Bootstrap 4, jQuery 3.3, Leaflet 1.4 — no build tools, no SPA framework, all server-rendered templates.

The data model uses a linked-list pattern for section ordering (`next_section`/`prev_section` ForeignKeys) and hierarchical self-references for sub-questions (`parent_question_id`). Questions store choices as a JSONField (`[{"code": 1, "name": {"en": "Yes"}}]`). Translations live in separate `SurveySectionTranslation` and `QuestionTranslation` models.

## Goals / Non-Goals

**Goals:**
- Visual CRUD for surveys, sections, questions, choices, sub-questions, and translations
- Drag-and-drop reordering for sections and questions
- Live inline preview showing the survey as respondents see it
- Map position picker for section geo settings
- Fit naturally into the existing server-rendered stack without introducing build tools

**Non-Goals:**
- Real-time collaborative editing (multiple users editing same survey simultaneously)
- Undo/redo history
- Conditional logic builder (show/hide questions based on previous answers)
- Survey versioning or draft/publish workflow
- Mobile-optimized editor (responsive but not mobile-first)
- Question templates or pre-built survey templates

## Decisions

### 1. HTMX + SortableJS over SPA framework

**Decision**: Use HTMX for partial page updates and SortableJS for drag-and-drop. No React/Vue.

**Alternatives considered**:
- **React SPA**: Most interactive, but requires a REST API layer, build toolchain (webpack/vite), and doubles the tech surface. Overkill for this project's scale.
- **Alpine.js + Fetch**: Lighter than React, but still requires manual AJAX handling. HTMX eliminates this boilerplate.

**Rationale**: HTMX (14KB) and SortableJS (10KB) are CDN-loaded, require zero build config, and work with existing Django templates. The editor needs partial swaps (add question → append to list) and drag-and-drop — both are first-class in these libraries. The server stays the single source of truth for all state.

### 2. Separate editor_views.py instead of extending views.py

**Decision**: Create a new `survey/editor_views.py` for all editor views.

**Rationale**: `views.py` (648 lines) handles the public survey-taking flow. Editor views have different auth requirements (`@login_required`), different response types (HTML fragments for HTMX), and different URL patterns. Separating them avoids a 1000+ line file and makes the editor self-contained.

### 3. Iframe-based live preview

**Decision**: Use an `<iframe>` pointing to a preview endpoint that renders the existing `survey_section.html` template in read-only mode.

**Alternatives considered**:
- **Client-side preview**: Build preview rendering in JS. Requires duplicating all form/widget logic client-side.
- **Server-Sent Events**: Push preview HTML via SSE on every change. More complex infrastructure.

**Rationale**: The iframe reuses the exact same templates that respondents see — zero duplication, pixel-perfect accuracy. Reloading the iframe after each HTMX swap adds ~200ms latency, acceptable for an editor. A `preview=True` context flag disables form submission and navigation in the preview.

### 4. Linked-list reorder via SortableJS callback

**Decision**: On drag-end, SortableJS sends the new section order as an array of IDs. The server rebuilds the entire linked list (`next_section`/`prev_section` + `is_head`).

**Alternatives considered**:
- **Switch to integer ordering**: Replace linked list with `order_number` field. Simpler reorder logic but requires a migration and changes to the survey-taking flow which traverses `next_section`.

**Rationale**: Keep the existing linked-list model to avoid migration risk and survey-taking flow changes. The reorder endpoint receives the full ordered array and rebuilds links in a single transaction — simple and atomic.

### 5. Question form in modal, section form inline

**Decision**: Sections are edited inline in the center panel (title, subheading, code fields always visible). Questions are edited in a Bootstrap modal (too many fields to inline: name, type, choices, color, icon, image, required, translations).

**Rationale**: Sections have few fields (3-4). Questions have 8+ fields plus dynamic choices and translations. A modal keeps the question list clean while providing ample space for the form.

### 6. Choices editor as dynamic form rows

**Decision**: The choices JSONField is edited via dynamic HTML rows (code + name per language) with add/remove buttons and vanilla JS.

**Rationale**: The choices structure `[{"code": N, "name": {"en": "...", "ru": "..."}}]` maps naturally to a table with columns for code and each language. On form submit, JS serializes rows to JSON and sets a hidden input. This avoids requiring users to write JSON manually (the current admin experience).

## Risks / Trade-offs

- **[No undo]** → Changes save immediately to the database. Users can re-edit, but there's no revert. Mitigation: The export feature provides full backup before editing.
- **[Preview iframe delay]** → ~200-300ms reload on each change. Mitigation: Debounce iframe reload (500ms) so rapid edits don't cause flicker.
- **[Linked-list corruption]** → If reorder fails mid-transaction, linked list could be inconsistent. Mitigation: Wrap reorder in `transaction.atomic()` and rebuild all links from scratch (not incremental).
- **[No concurrent edit protection]** → Two users editing the same survey can overwrite each other's changes. Mitigation: Acceptable for current single-user usage. Can add optimistic locking later.
- **[Large survey performance]** → A survey with 50+ questions per section could slow the DOM. Mitigation: Not expected in practice — current surveys have 5-15 questions per section.
