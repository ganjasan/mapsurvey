## 1. Model & Migrations

- [x] 1.1 Add `STATUS_CHOICES` tuple to `models.py` (draft, testing, published, closed, archived)
- [x] 1.2 Add `status` CharField to `SurveyHeader` (max_length=20, default="draft", choices=STATUS_CHOICES)
- [x] 1.3 Add `password_hash` CharField to `SurveyHeader` (max_length=128, null=True, blank=True)
- [x] 1.4 Add `test_token` UUIDField to `SurveyHeader` (default=uuid.uuid4, unique=True)
- [x] 1.5 Add model methods: `set_password()`, `check_password()`, `has_password()`, `clear_password()`
- [x] 1.6 Add model methods: `regenerate_test_token()`, `get_test_url(request)`
- [x] 1.7 Add model methods: `can_accept_responses()`, `can_transition_to(new_status)`
- [x] 1.8 Created 3-step migration (0015 schema, 0016 data, 0017 finalize)
- [x] 1.9 Create data migration: set `status='published'` for all existing surveys, `status='archived'` where `is_archived=True`

## 2. Access Control

- [x] 2.1 Create `survey/access_control.py` with `check_survey_access(request, survey)` function
- [x] 2.2 Implement draft check: return 404 for non-editor/owner users
- [x] 2.3 Implement testing check: validate token from `?token=` param or session, else show password form
- [x] 2.4 Implement published check: if password set and not in session, redirect to password page
- [x] 2.5 Implement closed/archived check: render "survey closed" page for non-editors
- [x] 2.6 Implement editor/owner bypass for all states

## 3. Password & Token Views

- [x] 3.1 Create `survey_password_gate` view in `views.py` at `/surveys/<slug>/password/`
- [x] 3.2 Create `survey_password.html` template (form with password input, survey name, error display)
- [x] 3.3 Create `survey_closed.html` template (closed message with survey name, back-to-home link)
- [x] 3.4 Add URL patterns: `surveys/<str:survey_slug>/password/` → `survey_password_gate`

## 4. Public View Integration

- [x] 4.1 Add `check_survey_access()` call to `survey_header` view (after `resolve_survey`)
- [x] 4.2 Add `check_survey_access()` call to `survey_section` view
- [x] 4.3 Add `check_survey_access()` call to `survey_language_select` view
- [x] 4.4 Modify `index` view: add `.exclude(status='draft')` to landing page query
- [x] 4.5 Add `check_survey_access()` call to `survey_thanks` view (skip if user has active session)

## 5. Editor Lifecycle Endpoints

- [x] 5.1 Add `editor_survey_transition` view to `editor_views.py` (POST, owner-only, validates + updates status)
- [x] 5.2 Implement test data cleanup logic (delete SurveySessions when `clear_test_data=true` on testing→published)
- [x] 5.3 Implement `is_archived=True` sync when transitioning to archived
- [x] 5.4 Add `editor_survey_password` view to `editor_views.py` (set/remove/regenerate_token actions)
- [x] 5.5 Add URL patterns: `editor/surveys/<uuid>/transition/`, `editor/surveys/<uuid>/password/`

## 6. Template Filter

- [x] 6.1 Create `survey/templatetags/survey_filters.py` with `status_badge_class` filter (draft→secondary, testing→warning, published→success, closed→info, archived→dark)

## 7. Dashboard UI

- [x] 7.1 Add "Status" column to survey table in `editor.html`
- [x] 7.2 Add status badge per survey row using `status_badge_class` filter
- [x] 7.3 Add archived filter: exclude `status=archived` by default, add "Show Archived" / "Hide Archived" toggle link
- [x] 7.4 Update `editor` view in `views.py`: handle `show_archived` query parameter

## 8. Editor Header UI

- [x] 8.1 Add status badge to editor header bar in `survey_detail.html`
- [x] 8.2 Add transition dropdown with state-appropriate actions (owner-only)
- [x] 8.3 Add password management button (lock icon) in editor header
- [x] 8.4 Create `editor/partials/survey_password_modal.html` (password status, set/change/remove form, test URL with copy button, regenerate token button)
- [x] 8.5 Add publish confirmation modal with "Delete test responses" checkbox for testing→published transition

## 9. Serialization

- [x] 9.1 Add `status` and `has_password` fields to `serialize_survey_to_dict()` in `serialization.py`
- [x] 9.2 Update `create_survey_header()` to read `status` from data (default `draft`), never import `password_hash` or `test_token`
- [x] 9.3 Add warning message when importing survey with `has_password=true`

## 10. Tests

- [x] 10.1 Test `can_transition_to()`: all valid transitions return `(True, "")`, all invalid return `(False, error)`
- [x] 10.2 Test pre-conditions: draft→testing fails without password, fails without sections/questions
- [x] 10.3 Test `set_password()` / `check_password()` / `has_password()` / `clear_password()`
- [x] 10.4 Test `check_survey_access()`: draft→404, testing with valid token→allowed, testing without token→password page, published without password→allowed, published with password→password page, closed→closed page
- [x] 10.5 Test `survey_password_gate` view: correct password sets session and redirects, incorrect shows error
- [x] 10.6 Test `editor_survey_transition` endpoint: valid transition→204, invalid→400, non-owner→403
- [x] 10.7 Test test data cleanup: sessions deleted when `clear_test_data=true`
- [x] 10.8 Test serialization roundtrip: export with status, import defaults to draft, password not exported
- [ ] 10.9 Test data migration: existing surveys get `status=published`, archived surveys get `status=archived` (verified via manual data migration code review)
- [x] 10.10 Test landing page: draft surveys excluded from listing
