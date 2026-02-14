## Context

The platform currently has no multi-tenancy or access control:

- `Organization` model has only a `name` field — no relationship to users
- `SurveyHeader.organization` is nullable, optional, and never enforced
- `editor()` view returns `SurveyHeader.objects.all()` — every authenticated user sees every survey
- All editor views use `@login_required` with zero ownership or permission checks
- `django-registration` is installed and configured (activation backend, email templates exist) but the sign-up link is hidden from the UI
- Standard `django.contrib.auth.User` model — no custom user model

The registration templates (`django_registration/registration_form.html`, etc.) and URL routes (`accounts/`) already exist and are functional — they just need to be exposed in the UI and enhanced with org-creation-on-signup logic.

## Goals / Non-Goals

**Goals:**
- Open self-service registration with email activation
- Personal organization created automatically on signup
- Multi-org membership with 4 roles (owner, admin, editor, viewer)
- Organization switching (active org stored in session)
- All editor views filtered by active org and gated by role
- Per-survey access control: survey owner + org owner/admin manage collaborators with 3 survey roles (owner/editor/viewer)
- Invitation system for adding users to organizations
- Member management UI (list, change role, remove)
- Safe migration: existing data moved to default "Mapsurvey" organization

**Non-Goals:**
- Custom user model (use stock `django.contrib.auth.User`)
- API authentication (JWT, OAuth) — admin/editor only uses session auth
- Organization billing/plans — out of scope for this change
- Public survey access changes — respondents don't need auth

## Decisions

### 1. Membership model instead of Django Groups

**Decision:** Create a `Membership` model (User FK, Organization FK, role CharField) rather than using Django's built-in Groups/Permissions system.

**Rationale:** Django groups are global (not scoped to an organization). We need per-org roles — the same user can be owner of Org A and viewer in Org B. A simple Membership M2M-with-role model is the standard pattern for multi-tenant Django apps.

**Alternatives considered:**
- Django Groups + per-object permissions via `django-guardian`: Over-engineered for our 4-role model; adds dependency
- Roles as a separate model: Unnecessary — 4 fixed roles work as a CharField with choices

### 2. Active organization in session

**Decision:** Store `active_org_id` in `request.session`. Middleware populates `request.active_org` on each request. Org switcher writes to session and redirects.

**Rationale:** Simple, no database writes per request, works with existing Django session infrastructure. Fallback: if session has no active org, use the user's first membership.

**Alternatives considered:**
- URL prefix (`/org/<slug>/editor/`): Would require rewriting every URL pattern; breaks existing bookmarks
- Cookie: Same effect as session but harder to secure; session is already available

### 3. Organization slug field

**Decision:** Add `slug` field to Organization (unique, auto-generated from name, editable). Used in org management URLs and as display identifier.

**Rationale:** Needed for clean URLs (`/org/my-team/members/`). Auto-generated from name but editable.

### 4. Role hierarchy

**Decision:** Four roles with hierarchical permissions:
- **owner** — full control: manage members, manage org settings, all editor actions, transfer/delete org. At least one owner required per org.
- **admin** — manage members (except owners), all editor actions
- **editor** — create/edit/delete surveys, import/export
- **viewer** — read-only access to editor dashboard and survey preview (no create/edit/delete)

**Rationale:** Matches common SaaS patterns (GitHub, Notion). Four levels provide enough granularity without over-complicating the permission model.

### 5. Invitation via email

**Decision:** Owners/admins create invitations (email + role). System sends email with unique token link. Recipient clicks link → if registered, membership created; if not, redirected to registration first, then membership created.

**Rationale:** Email-based invitation is the standard approach. Token-based is simple and doesn't require the invitee to already have an account.

**Alternatives considered:**
- Username-based invite: Requires invitee to register first; worse UX
- Link sharing (no email): Less secure, no audit trail

### 6. Personal organization on registration

**Decision:** When a new user registers, the `post_save` signal (or registration backend hook) creates a personal organization named after the user (e.g., "username's workspace") with the user as owner.

**Rationale:** Users should immediately have a workspace to create surveys in. Matches the user's answer "Персональная организация сразу при регистрации."

### 7. Migration strategy

**Decision:** Data migration creates a default "Mapsurvey" organization. All existing `SurveyHeader` records are assigned to it. All existing users get owner membership. Then `SurveyHeader.organization` becomes non-null.

**Rationale:** Preserves all existing data, gives all current users full access, and makes the FK transition safe (no orphaned surveys).

### 8. Per-survey access control via SurveyCollaborator

**Decision:** Create a `SurveyCollaborator` model (User FK, SurveyHeader FK, role CharField with choices: owner/editor/viewer). When a user creates a survey, they automatically become survey owner. Survey owners and org owners/admins can add/remove/change collaborators.

**Role resolution (two-layer model):**
- Org-level role (Membership) provides **baseline access** to all surveys in the org
- Survey-level role (SurveyCollaborator) can **override** for a specific survey
- Effective permission = max(org_role_implied_survey_access, survey_collaborator_role)
- Org owner/admin → implicit full control over all surveys (no SurveyCollaborator needed)
- Org editor → can create surveys and edit their own; other surveys only if explicitly added as collaborator
- Org viewer → read-only by default; can be granted editor/owner on specific surveys

**Mapping org roles to implicit survey access:**
- owner/admin → survey owner (full control on all surveys)
- editor → survey editor only on surveys they created; no access to others unless added as collaborator
- viewer → survey viewer on all surveys (read-only)

**Rationale:** This gives fine-grained control while keeping the common case simple. Most users won't need per-survey overrides — org roles cover the typical workflow. But for teams where some members should only see specific surveys, collaborator entries provide that control.

**Alternatives considered:**
- Org-level only (no per-survey): Too coarse — user asked for per-survey management
- ACL/permission matrix: Over-engineered for 3 roles; adds complexity
- Separate "project" grouping layer: Adds another entity; surveys are already the natural unit

### 9. Permission enforcement via decorator

**Decision:** Create `@org_permission_required(min_role='editor')` decorator that:
1. Checks user has active org in session
2. Checks user has membership with sufficient role (org-level baseline)
3. For survey-specific views, checks effective permission = max(org baseline, survey collaborator role)
4. Returns 403 if insufficient permissions

Helper function `get_effective_survey_role(user, survey)` computes the max of org-level implied role and explicit SurveyCollaborator role.

**Rationale:** Decorator pattern is consistent with existing `@login_required` usage. Centralizes two-layer permission logic in one place.

## Risks / Trade-offs

- **Session stale after role change** — If an admin removes a user's membership, the user's session still has `active_org_id` until they switch or re-login → Mitigation: permission decorator always re-checks membership from DB, never trusts session role
- **Email delivery for registration/invitations** — Current email config is `localhost:25` which won't work in most deployments → Mitigation: document required email backend setup in `.env.example`; support console email backend for development
- **Organization name collisions** — Multiple orgs could have the same name → Mitigation: slug is unique; name is display-only
- **Existing surveys without organization** — After migration, all surveys belong to "Mapsurvey" org → Mitigation: clearly documented; users can create new orgs and move surveys later (moving surveys between orgs is a future feature, not in this change)

## Migration Plan

1. Add `slug` field to Organization (nullable first)
2. Add `Membership` model
3. Add `Invitation` model
4. Add `SurveyCollaborator` model
5. Add `SurveyHeader.created_by` (nullable User FK)
6. Data migration: create "Mapsurvey" org, assign all existing users as owners, assign all surveys
7. Populate slug for existing orgs
8. Make `Organization.slug` non-null + unique
9. Make `SurveyHeader.organization` non-null (remove `blank=True, null=True`)

Rollback: Reverse migrations restore nullable org FK and drop Membership/Invitation/SurveyCollaborator tables. No data loss.

## Open Questions

- Should we allow users to delete their personal organization? (Probably no — always need at least one org)
- Should org transfer (change owner) be in this change or deferred? (Deferred — can be done via admin for now)
