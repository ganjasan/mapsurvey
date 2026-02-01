## Why

The editor page (`/editor`) displays a list of surveys with actions like Edit, Download Data, and Export. There's a "Delete" link shown but it's non-functional (just `href="#"`). Users need a way to delete surveys they no longer need directly from the editor interface instead of going through the Django admin.

## What Changes

- Add a functional Delete button for each survey in the editor table
- Implement a confirmation modal to prevent accidental deletions
- Create a backend endpoint to handle survey deletion with proper authorization
- Delete cascade handles related data (sessions, answers, sections, questions)

## Capabilities

### New Capabilities
- `survey-deletion`: Ability to delete surveys via the editor interface with confirmation dialog and proper authorization checks

### Modified Capabilities
None - this adds new functionality without changing existing spec-level behavior.

## Impact

- **Views**: New `delete_survey` view in `survey/views.py`
- **URLs**: New URL pattern for delete endpoint
- **Templates**: Update `editor.html` to add confirmation modal and wire up delete button
- **Models**: No changes needed (Django's CASCADE delete handles related data)
- **Authorization**: Only authenticated users can delete surveys (consistent with existing editor access)
