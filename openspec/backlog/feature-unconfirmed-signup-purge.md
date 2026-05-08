# Auto-Purge of Unconfirmed Signups

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Periodic job that deletes accounts (or pending-signup tokens, depending on implementation choice in [feature-email-verification-before-account.md](feature-email-verification-before-account.md)) where the user never confirmed within N days and never created any content.

This is housekeeping: even after Phase 1+2 defenses ship, some bots will get through, and some real users will sign up but never verify. Both should be removed automatically.

## Goals

- Keep `auth_user` clean of inactive cruft.
- Remove bot/abandoned accounts without manual ops (the 2026-05-08 cleanup of 41 accounts took 30 minutes of manual SQL — should be a cron, not a fire drill).
- Improve quality of "active users" metrics.

## Proposed Rules

| Rule | Action | Window |
|------|--------|--------|
| Pending signup never confirmed | Delete pending-signup token | 7 days |
| User created, never logged in after registration, no surveys, no responses | Delete | 30 days |
| User logged in once, no surveys, no responses, no logins for 90 days | Notify, then delete | 90 + 14 days |

The third rule is conservative — it gives us a notification email opportunity ("come back, here's what's new") before purging. Discuss with outreach campaign before enabling.

## Scope

### In Scope

- Django management command `purge_inactive_users` (idempotent, dry-run flag).
- Render cron job entry to run nightly.
- Audit log table `auth_user_purged` capturing `(user_id, username, email, deletion_reason, deleted_at)` for compliance/incident-response.
- Foreign-key chain handling (the 2026-05-08 incident exposed: we have to delete from `survey_membership`, `auth_user_groups`, `auth_user_user_permissions` before `auth_user` — codify that order).

### Out of Scope

- Soft-delete vs hard-delete debate — go with hard-delete + audit log. Soft-delete on auth tables is a maintenance burden Django doesn't help with.
- "Unsubscribe me" UI flows — orthogonal.

## Open Questions

- Do we honor a "preserve my account please" flag if the user opts in? Probably overkill for v1 — re-registration is cheap.
- Email notifications before deletion (the rule-3 case) — coordinate with the user-outreach campaign so we don't double-notify.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling: [feature-email-verification-before-account.md](feature-email-verification-before-account.md)
- Sibling: [improvement-signup-anomaly-dashboard.md](improvement-signup-anomaly-dashboard.md)
