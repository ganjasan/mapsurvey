## 1. Models and Migrations

- [x] 1.1 Add `slug` field to Organization model (SlugField, unique, max 100)
- [x] 1.2 Create `Membership` model (user FK, organization FK, role CharField, joined_at DateTimeField; unique_together user+org)
- [x] 1.3 Create `Invitation` model (email, organization FK, role, token UUID, invited_by FK, created_at, accepted_at nullable)
- [x] 1.4 Create `SurveyCollaborator` model (user FK, survey FK, role CharField; unique_together user+survey)
- [x] 1.5 Add `created_by` field to SurveyHeader (nullable FK to User, SET_NULL)
- [x] 1.6 Write data migration: create "Mapsurvey" org with slug "mapsurvey", assign all existing users as owners, assign all unassigned surveys, create SurveyCollaborator owner entries
- [x] 1.7 Write migration to make SurveyHeader.organization non-null (remove null=True, blank=True)
- [x] 1.8 Run `makemigrations` and verify migration chain

## 2. Middleware and Permission Utilities

- [x] 2.1 Create `ActiveOrgMiddleware` — reads `active_org_id` from session, sets `request.active_org`, falls back to first membership if invalid
- [x] 2.2 Add middleware to `settings.MIDDLEWARE` (after AuthenticationMiddleware)
- [x] 2.3 Implement `get_effective_survey_role(user, survey)` helper — resolves max of org baseline and SurveyCollaborator role
- [x] 2.4 Create `@org_permission_required(min_role)` decorator — checks org membership, returns 403 if insufficient
- [x] 2.5 Create `@survey_permission_required(min_role)` decorator — checks effective survey role, returns 403/404 if insufficient
- [x] 2.6 Write tests for permission resolution logic (org owner, admin, editor with/without collaborator, viewer with override)

## 3. Registration and Authentication

- [x] 3.1 Add "Register" link to login template (`registration/login.html`)
- [x] 3.2 Create custom registration backend or signal to create personal org on user activation
- [x] 3.3 Update registration templates styling to match app design
- [x] 3.4 Configure email backend settings (add `EMAIL_BACKEND` env var support, console backend default in dev)
- [x] 3.5 Add logout link to editor navigation
- [x] 3.6 Write tests: registration flow, personal org creation on activation, login redirect

## 4. Organization Management Views

- [x] 4.1 Create org creation form and view at `/org/new/`
- [x] 4.2 Create org settings view at `/org/<slug>/settings/` (name, slug editing; owner-only)
- [x] 4.3 Create member list view at `/org/<slug>/members/` (list members + pending invitations)
- [x] 4.4 Create change-role view (owner/admin only; admin cannot change owner roles)
- [x] 4.5 Create remove-member view (owner/admin only; cannot remove last owner)
- [x] 4.6 Add URL patterns for org management routes
- [x] 4.7 Create templates: org_new.html, org_settings.html, org_members.html
- [x] 4.8 Write tests: org CRUD, member management, role restrictions

## 5. Invitation System

- [x] 5.1 Create invitation form (email + role selector)
- [x] 5.2 Create send-invitation view (creates Invitation, sends email with token link)
- [x] 5.3 Create accept-invitation view at `/invitations/<token>/accept/` — handle registered and unregistered users
- [x] 5.4 Handle invitation token in registration flow (auto-accept after activation)
- [x] 5.5 Add pending invitations display to member list page
- [x] 5.6 Create invitation email template
- [x] 5.7 Add URL patterns for invitation routes
- [x] 5.8 Write tests: send invitation, accept as existing user, accept as new user, expired invitation, duplicate invitation

## 6. Organization Switcher

- [x] 6.1 Create context processor to inject active org and user's org list into templates
- [x] 6.2 Create switch-org view (POST, sets session `active_org_id`, redirects to `/editor/`)
- [x] 6.3 Add org switcher dropdown to editor base template (show for multi-org users, plain name for single-org)
- [x] 6.4 Set `active_org_id` on login (in login redirect or middleware fallback)
- [x] 6.5 Write tests: switcher visibility, switch action, fallback on login

## 7. Editor Views — Permission Integration

- [x] 7.1 Update `editor()` dashboard view: filter surveys by active org + user access (org owner/admin see all, editor sees own+collaborated, viewer sees all read-only)
- [x] 7.2 Update `editor_survey_create()`: check org editor+ role, set organization=active_org, created_by=current_user, create SurveyCollaborator owner
- [x] 7.3 Update `editor_survey_detail()`: check effective survey role, pass role to template for read-only mode
- [x] 7.4 Update `editor_survey_settings()`: check survey owner or org owner/admin
- [x] 7.5 Update section CRUD views: check effective survey role >= editor
- [x] 7.6 Update question CRUD views: check effective survey role >= editor
- [x] 7.7 Update reorder views (sections, questions): check effective survey role >= editor
- [x] 7.8 Remove `organization` field from SurveyHeaderForm (auto-assigned to active org)
- [x] 7.9 Write tests: permission checks for all editor view actions (create, edit, delete, reorder as viewer/editor/owner)

## 8. Export/Import — Permission Integration

- [x] 8.1 Update `export_survey()` view: check effective survey role >= viewer, verify survey belongs to active org
- [x] 8.2 Update `import_survey()` view: check org role >= editor, set organization=active_org, created_by=current_user, create SurveyCollaborator
- [x] 8.3 Update `delete_survey()` view: check effective survey role == owner or org role owner/admin
- [x] 8.4 Write tests: export/import/delete permission checks

## 9. Collaborator Management UI

- [x] 9.1 Create collaborator list partial template (for survey settings page)
- [x] 9.2 Create add-collaborator view (select org member + role; survey owner or org owner/admin only)
- [x] 9.3 Create change-collaborator-role view
- [x] 9.4 Create remove-collaborator view (cannot remove last survey owner)
- [x] 9.5 Add URL patterns for collaborator management
- [x] 9.6 Integrate collaborator section into survey settings template
- [x] 9.7 Write tests: add/change/remove collaborators, last-owner protection

## 10. Dashboard Template Updates

- [x] 10.1 Update editor dashboard template: conditionally show/hide New Survey, Import, Edit, Delete, Export buttons based on user's effective role
- [x] 10.2 Update editor base template: add org switcher, logout link
- [x] 10.3 Update survey editor template: show/hide edit controls based on effective survey role (read-only mode for viewers)
- [x] 10.4 Verify all template links use correct permission-aware URL patterns

## 11. CLI Commands Update

- [x] 11.1 Update `import_survey` management command: accept optional `--organization` argument, default to first org or "Mapsurvey"
- [x] 11.2 Ensure `export_survey` CLI works without session context (no permission check for CLI)
- [x] 11.3 Write tests: CLI import with org assignment

## 12. Final Integration and Cleanup

- [x] 12.1 Run full test suite and fix regressions
- [x] 12.2 Verify migration sequence (forward and reverse)
- [x] 12.3 Update `.env.example` with email backend settings
- [ ] 12.4 Smoke test: register → activate → create org → invite user → create survey → add collaborator → switch org
