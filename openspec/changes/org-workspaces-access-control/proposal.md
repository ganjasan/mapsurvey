## Why

The platform currently has no access control: any authenticated user sees and can edit all surveys. Registration is disabled in the UI, and the Organization model is a bare name field with no user relationships. To launch as an open-source project and cloud service, we need open registration, multi-tenant organization workspaces, role-based permissions, and survey ownership so that teams can collaborate safely.

## What Changes

- **Enable open registration** — activate `django-registration` sign-up flow with email activation; create a personal organization for each new user automatically
- **Add Membership model** — M2M relationship between User and Organization with role field (owner / admin / editor / viewer)
- **Organization switcher** — users can belong to multiple organizations and switch between them; active org stored in session
- **Survey ownership** — tie every SurveyHeader to an organization; filter editor views to show only surveys belonging to the active organization; survey creator becomes survey owner
- **Per-survey access control** — SurveyCollaborator model with 3 roles (owner / editor / viewer) per survey; survey owner and org owner/admin can manage collaborators; org-level role provides baseline access, per-survey role can restrict or extend
- **Permission checks** — enforce role-based access at both org and survey level in all editor views (create, edit, delete, export, import); effective permission = max(org role, survey role)
- **Invitation system** — org owners/admins can invite users by email to join their organization with a specific role
- **User management UI** — org owners/admins can view members, change roles, and remove members
- **Data migration** — create a default "Mapsurvey" organization, assign all existing users and surveys to it; existing users become owners

## Capabilities

### New Capabilities
- `user-registration`: Open registration flow with email activation, personal org creation on signup, login/logout pages
- `org-membership`: Organization CRUD, Membership model (User-Org M2M with roles: owner/admin/editor/viewer), invitation system, member management UI
- `org-access-control`: Permission checks in editor/export/import/delete views, survey filtering by active org, role-based UI visibility, org switcher, per-survey collaborator management (SurveyCollaborator model with owner/editor/viewer roles)

### Modified Capabilities
- `survey-editor`: Editor views filter surveys by active organization; create/edit/delete actions check org and survey-level roles; "New Survey" auto-assigns to active org with creator as survey owner; collaborator management UI in survey settings
- `survey-serialization`: Import assigns survey to active organization; export restricted to users with at least viewer access (org or survey level)
- `survey-deletion`: Delete restricted to survey owner + org owner/admin roles

## Impact

- **Models**: `Organization` gains slug, `Membership` model (new), `SurveyCollaborator` model (new), `SurveyHeader` gets non-null org FK + `created_by` user FK
- **Views**: `views.py`, `editor_views.py` — permission decorators/mixins, org context injection, survey filtering
- **Templates**: editor dashboard, editor base (org switcher), new registration/login/invitation templates, member management pages
- **URLs**: new routes for registration, org management, member management, invitations
- **Settings**: enable `django-registration` in `INSTALLED_APPS`, configure email backend, activation settings
- **Forms**: registration form, invitation form, org creation form, member role form
- **Migrations**: add Membership model, alter Organization, alter SurveyHeader.organization (non-null), data migration for default org
