# Audit Trail (edit history log)

**Type**: feature
**Priority**: low
**Area**: backend
**Epic**: data-management
**Created**: 2026-04-05

> Note: this file was created retroactively on 2026-07-23 — INDEX #59 referenced it as a
> dangling link. The **operations-audit slice** (destructive/lifecycle actions: delete,
> restore, purge, status transitions, password ops) was promoted to the OpenSpec change
> `survey-deletion-safety` after the Holly/Agnew::Beck incident (a user hard-deleted a
> month of work in 13 seconds with no trace and no recovery path). What remains here is
> the **content edit-history** slice.

## Description

Field-level edit history for survey content: who changed which question/section, when,
and what the previous value was. Complements the operations `AuditLog` (already shipped
in `survey-deletion-safety`), which records *that* something destructive happened but not
content diffs.

## Goals

- Answer "who changed this question and what did it say before?" for collaborating teams
  (org members + survey collaborators editing the same survey).
- Support undo of content edits (long-term; pairs with survey versioning).

## Scope Sketch

- Capture on editor CRUD endpoints: section/question create/edit/delete/reorder,
  choices edits, translation edits.
- Storage: append-only rows with survey uuid, object type/id, field, old/new values
  (JSON), actor, timestamp. Consider retention/compaction (content edits are chatty —
  drag-reorder can emit dozens of rows).
- Surface: per-survey "History" panel in the editor; admin view for support.

## Dependencies / Related

- Operations audit + trash/restore: shipped in `openspec/changes/survey-deletion-safety`.
- Survey versioning already snapshots published versions — edit history covers the
  gaps *between* versions, not the versions themselves.
