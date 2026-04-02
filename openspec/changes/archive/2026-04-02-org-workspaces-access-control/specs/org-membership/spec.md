## ADDED Requirements

### Requirement: Organization model with slug
The Organization model SHALL have a `name` (CharField, max 250) and a `slug` (SlugField, unique, max 100). The slug SHALL be auto-generated from the name on creation but editable afterward.

#### Scenario: Organization created with auto-slug
- **WHEN** an organization is created with name "My Research Lab"
- **THEN** the slug SHALL be auto-generated as "my-research-lab"

#### Scenario: Slug uniqueness enforced
- **WHEN** an organization is created with a name that generates a slug already in use
- **THEN** the system SHALL append a numeric suffix (e.g., "my-research-lab-2")

#### Scenario: Slug is editable
- **WHEN** an org owner updates the slug to "research-lab"
- **THEN** the Organization.slug is updated to "research-lab"

### Requirement: Membership model
The system SHALL have a `Membership` model representing the M2M relationship between User and Organization with a role. Fields: `user` (FK to User), `organization` (FK to Organization), `role` (CharField with choices), `joined_at` (DateTimeField, auto_now_add). The combination of (user, organization) SHALL be unique.

#### Scenario: Create membership
- **WHEN** a user is added to an organization with role "editor"
- **THEN** a Membership record is created with user, organization, role="editor", and joined_at set to current time

#### Scenario: Duplicate membership rejected
- **WHEN** a membership already exists for user+organization and another is created
- **THEN** the system SHALL raise a unique constraint violation

#### Scenario: Role choices
- **WHEN** a membership is created
- **THEN** the role field SHALL accept only: "owner", "admin", "editor", "viewer"

### Requirement: Organization CRUD
The system SHALL provide views for creating and editing organizations. Organization creation SHALL be available at `/org/new/`. Organization settings SHALL be available at `/org/<slug>/settings/`.

#### Scenario: Create organization
- **WHEN** an authenticated user submits the org creation form with name "City Planning Team"
- **THEN** an Organization is created with that name and auto-generated slug
- **AND** a Membership is created with user=current_user, role="owner"
- **AND** the session's `active_org_id` is set to the new organization
- **AND** the user is redirected to `/editor/`

#### Scenario: Edit organization name
- **WHEN** an org owner updates the organization name to "Urban Planning Team"
- **THEN** the Organization.name is updated

#### Scenario: Only owner can edit org settings
- **WHEN** a user with role "editor" accesses `/org/<slug>/settings/`
- **THEN** the system SHALL return 403

#### Scenario: Unauthenticated access denied
- **WHEN** an unauthenticated user accesses `/org/new/`
- **THEN** the system SHALL redirect to the login page

### Requirement: Member management
The system SHALL provide a member list and management UI at `/org/<slug>/members/`. Org owners and admins SHALL be able to view members, change roles, and remove members.

#### Scenario: List members
- **WHEN** an org member navigates to `/org/<slug>/members/`
- **THEN** the page SHALL display all members with their username, email, role, and joined date

#### Scenario: Owner changes member role
- **WHEN** an org owner changes a member's role from "viewer" to "editor"
- **THEN** the Membership.role is updated to "editor"

#### Scenario: Admin cannot change owner role
- **WHEN** an org admin attempts to change an owner's role
- **THEN** the system SHALL return 403

#### Scenario: Admin can change non-owner roles
- **WHEN** an org admin changes an editor's role to "viewer"
- **THEN** the Membership.role is updated to "viewer"

#### Scenario: Remove member
- **WHEN** an org owner removes a member from the organization
- **THEN** the Membership record is deleted
- **AND** all SurveyCollaborator records for that user within this org's surveys are deleted

#### Scenario: Cannot remove last owner
- **WHEN** an org has only one owner and that owner attempts to leave or be removed
- **THEN** the system SHALL reject the action with error "Cannot remove the last owner"

#### Scenario: Viewer cannot manage members
- **WHEN** a user with role "viewer" attempts to change another member's role
- **THEN** the system SHALL return 403

#### Scenario: Editor cannot manage members
- **WHEN** a user with role "editor" attempts to remove a member
- **THEN** the system SHALL return 403

### Requirement: Invitation system
The system SHALL allow org owners and admins to invite users by email. Invitations SHALL be stored in an `Invitation` model with fields: `email`, `organization` (FK), `role`, `token` (UUID, unique), `invited_by` (FK to User), `created_at`, `accepted_at` (nullable).

#### Scenario: Send invitation
- **WHEN** an org owner creates an invitation for "user@example.com" with role "editor"
- **THEN** an Invitation record is created with a unique token
- **AND** an email is sent to "user@example.com" with a link containing the token

#### Scenario: Accept invitation — existing user
- **WHEN** a registered user clicks the invitation link at `/invitations/<token>/accept/`
- **THEN** a Membership is created with the invited role
- **AND** the Invitation.accepted_at is set to current time
- **AND** the user is redirected to `/editor/`

#### Scenario: Accept invitation — new user
- **WHEN** an unregistered visitor clicks the invitation link
- **THEN** the system SHALL redirect to `/accounts/register/?invitation=<token>`
- **AND** after registration and activation, the Membership is created automatically

#### Scenario: Expired invitation
- **WHEN** an invitation link is clicked after 7 days
- **THEN** the system SHALL display "This invitation has expired"

#### Scenario: Already accepted invitation
- **WHEN** an invitation link is clicked after it has already been accepted
- **THEN** the system SHALL display "This invitation has already been used"

#### Scenario: Duplicate invitation for same email and org
- **WHEN** an invitation exists for "user@example.com" in Org A and another is created for the same email and org
- **THEN** the old invitation SHALL be replaced by the new one

#### Scenario: Admin cannot invite with owner role
- **WHEN** an org admin creates an invitation with role "owner"
- **THEN** the system SHALL reject with error "Only owners can invite owners"

#### Scenario: Invitation list
- **WHEN** an org owner/admin navigates to `/org/<slug>/members/`
- **THEN** pending invitations SHALL be displayed below the member list with email, role, and sent date

### Requirement: Organization switcher
The system SHALL display an organization switcher in the editor navigation for users who belong to multiple organizations. The active organization SHALL be stored in `request.session['active_org_id']`.

#### Scenario: Switcher visible for multi-org users
- **WHEN** a user who belongs to 2+ organizations views the editor
- **THEN** the navigation SHALL display a dropdown showing the active org name with other orgs as options

#### Scenario: Switcher hidden for single-org users
- **WHEN** a user who belongs to exactly 1 organization views the editor
- **THEN** the navigation SHALL display the org name without a dropdown

#### Scenario: Switch organization
- **WHEN** a user selects a different organization from the switcher
- **THEN** the session's `active_org_id` is updated to the selected org
- **AND** the user is redirected to `/editor/`

#### Scenario: Default active org on login
- **WHEN** a user logs in and has no `active_org_id` in session
- **THEN** the system SHALL set `active_org_id` to the user's first organization (by Membership.joined_at)

#### Scenario: Active org middleware
- **WHEN** an authenticated request is processed
- **THEN** middleware SHALL populate `request.active_org` from session's `active_org_id`
- **AND** if the user no longer has membership in that org, fall back to their first org
