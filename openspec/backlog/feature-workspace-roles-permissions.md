# Workspace roles & permissions (incl. read-only client access)

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

Granular roles on top of the existing workspace membership. Free keeps equal-rights
Members — collaborating with colleagues costs nothing. Pro adds differentiated access,
and the actual purchase trigger is **read-only guest access for the client**: the
municipality or funder can watch collection progress live without being able to edit,
delete, or publish anything.

That is precisely the shape a grant-funded project needs, and it is impossible to fake
by sharing a login.

## Roles sketch

| Role | Free | Pro | Can |
|------|------|-----|-----|
| Owner | ✅ | ✅ | everything incl. billing, deletion |
| Member | ✅ | ✅ | full edit on all workspace surveys |
| Editor (per-survey) | — | ✅ | edit only assigned surveys |
| Analyst | — | ✅ | see responses + analytics, no survey edits |
| Guest / Client | — | ✅ | read-only: response counts, results, no data export, no edits |

## Scope Sketch

- Role field on workspace membership + optional per-survey assignment.
- Enforcement in editor views, analytics views, export endpoints, and lifecycle
  transitions — not only in template rendering. Permission checks belong next to the
  queryset, not in the UI.
- Invite flow with role selection; guest invites should work without the guest needing to
  understand what Mapsurvey is (magic-link style, minimal onboarding).
- Guest-visible surface is deliberately narrow: live counts, the results view, and
  nothing that lets them alter or extract the dataset.

## Dependencies / Related

- `org-workspaces-access-control` (archived 2026-04-02) — the membership model this
  extends.
- [Audit trail](feature-audit-trail.md) (#59) — with multiple roles editing, "who changed
  this" stops being a nicety.
- [Plans & entitlements](feature-workspace-plans-entitlements.md) (#87) — gate.

## Notes

- Do not gate the number of Members. Team collaboration stays free; differentiated
  *rights* are what is sold.
