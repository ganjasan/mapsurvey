## 1. Backend

- [x] 1.1 Add `delete_survey` view in `survey/views.py` with `@login_required` decorator
- [x] 1.2 Handle POST requests only, return error/redirect for GET
- [x] 1.3 Look up survey by name, handle DoesNotExist with error message
- [x] 1.4 Delete survey and redirect to editor with success message
- [x] 1.5 Add URL pattern `editor/delete/<str:survey_name>/` in `survey/urls.py`

## 2. Frontend

- [x] 2.1 Add delete confirmation modal to `editor.html` (similar to import modal)
- [x] 2.2 Update Delete link to trigger modal with JavaScript setting survey name
- [x] 2.3 Add form inside modal with CSRF token, POST to delete endpoint

## 3. Testing

- [x] 3.1 Write test for successful survey deletion
- [x] 3.2 Write test for unauthenticated user redirect
- [x] 3.3 Write test for deleting non-existent survey
- [x] 3.4 Write test for cascade deletion of related data
