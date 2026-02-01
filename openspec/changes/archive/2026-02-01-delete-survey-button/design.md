## Context

The editor page (`/editor`) is a dashboard for authenticated users to manage surveys. Currently it displays surveys in a table with Edit, Download Data, and Export actions. A "Delete" link exists but is non-functional. Users must use Django admin to delete surveys.

The data model uses CASCADE deletes: deleting a `SurveyHeader` automatically removes related `SurveySection`, `Question`, `SurveySession`, and `Answer` records.

## Goals / Non-Goals

**Goals:**
- Add a working delete button for each survey in the editor
- Require user confirmation before deletion to prevent accidents
- Ensure only authenticated users can delete surveys
- Provide clear feedback on successful/failed deletion

**Non-Goals:**
- Soft delete or archival functionality (hard delete only)
- Bulk delete operations
- Permission system beyond login_required (no per-survey ownership checks)
- Undo/restore functionality

## Decisions

### 1. Confirmation via Bootstrap modal (not browser confirm())

**Decision**: Use a Bootstrap modal dialog for delete confirmation.

**Rationale**: Consistent with existing import modal pattern in editor.html. Provides better UX and styling than browser's native confirm(). Allows displaying survey name in the confirmation message.

**Alternatives considered**:
- Browser `confirm()`: Simpler but inconsistent with existing UI patterns
- Separate confirmation page: Unnecessary complexity for a simple action

### 2. POST request with CSRF protection

**Decision**: Use POST method with Django CSRF token for the delete action.

**Rationale**: DELETE is a destructive operation. GET requests should be idempotent. POST with CSRF prevents cross-site request forgery attacks.

### 3. Single modal with JavaScript to set survey name

**Decision**: Use one modal in the template, updating its content via JavaScript when delete is clicked.

**Rationale**: Avoids creating N modals for N surveys. Keeps template clean.

### 4. Redirect back to editor with flash message

**Decision**: After deletion, redirect to `/editor/` with a Django messages success/error notification.

**Rationale**: Consistent with existing import functionality pattern. User sees feedback in the same context.

## Risks / Trade-offs

- **[Risk] Accidental deletion of survey with data** → Mitigation: Confirmation modal shows survey name; modal requires explicit button click
- **[Risk] Loss of survey data is permanent** → Mitigation: Documented as non-goal; users can export before deletion
- **[Trade-off] No ownership checks** → Simple auth model; acceptable for current single-organization use case
