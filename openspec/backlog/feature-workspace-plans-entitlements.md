# Workspace plans & entitlements (Free / Pro)

**Type**: feature
**Priority**: very high
**Area**: backend
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

Foundation for the Free/Pro split: a plan attached to a workspace (the existing
`Organization`), plus a single entitlement-checking layer that every Pro feature calls.
Without this, each Pro feature invents its own gate and the tier becomes impossible to
change.

## Goals

- One authoritative answer to "does this workspace have feature X?" usable from views,
  templates, and HTMX partials.
- Plan changes take effect without a deploy.
- Grandfathering is expressible as data, not as code branches.

## Scope Sketch

- `Plan` (free / pro) on the workspace, plus a per-workspace override map for
  grandfathered and manually granted entitlements.
- `has_entitlement(workspace, key)` helper + template tag; a decorator for editor views.
- Entitlement keys mirror the epic table (`geo_zone`, `public_results`, `custom_domain`,
  `white_label`, `roles`, `audit_trail`, `ai_create`, `ai_analytics`, `funnel`,
  `advanced_analytics`).
- Upsell surface when a locked feature is touched — show what it does, never hide it.
  A feature the free user cannot see is a feature they will never buy.

## Grandfathering (hard requirement)

Existing accounts keep everything they already use on their current projects,
indefinitely. Implementation: a one-off backfill that stamps per-workspace overrides for
accounts created before the cutover, scoped to their existing surveys. New surveys and
new accounts fall under the plan. See the rollout section in
[epics/pro-tier.md](epics/pro-tier.md).

## Notes

- `org-workspaces-access-control` (archived 2026-04-02) already gives the workspace
  container this hangs off.
- Do NOT gate response volume, survey count, question count, or exports — see the Free
  list in the epic.
- Ship this before any individual Pro feature; it is the ordering constraint for the
  whole epic.
