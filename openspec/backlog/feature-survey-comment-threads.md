# Comment threads anchored to survey objects

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: team-collaboration
**Created**: 2026-09-15
**Related**: [Workspace roles & permissions](feature-workspace-roles-permissions.md), [Questions on overlay features](feature-questions-on-overlay-features.md) (respondent-side comments — a different thing)

## Description

Workspace members can open a comment thread on a specific object inside a survey — a
question, a section, a public-results block, an individual answer on the responses map —
discuss it, propose a change, and mark the thread resolved. Threads live in the editor
next to the object they are about, and every reply goes out by email with a link straight
into the thread.

Not a chat. A single per-survey chat loses the context that is the whole point; the value
is the anchor. Model: Google Docs / Figma comments, not Slack.

## Why now

The owner raised it on 2026-09-15 while onboarding City of Olney: the client is about to
send "preliminary notes" by email, we will transcribe them into edits by hand, and a week
later nobody remembers which question note three referred to.

**The first user is us, not clients talking to each other.** Prod on 2026-09-15:

| Members in workspace | Workspaces |
|---|---|
| 1 | 374 |
| 2 | 10 |
| 3 | 7 |

374 of 391 workspaces are one person; clients have nobody to discuss with. But the 17
multi-member workspaces are exactly the top leads (Decisio, SPEN, BMP2026, City of Olney),
and the pattern in every one of them is us sitting inside the client's workspace finishing
the survey for them (memory `project_service_model_hypothesis`). Threads are the working
surface for that service, which is why this sits in the pro-tier epic next to
[roles & permissions](feature-workspace-roles-permissions.md).

## Scope sketch

- `CommentThread` (survey FK, generic anchor: question | section | results block | answer,
  status open/resolved, created_by) + `Comment` (thread FK, author, body, created_at).
  Anchor via explicit nullable FKs rather than a GenericForeignKey so deletion cascades
  and querysets stay simple.
- Editor: a comment affordance on every anchorable object, a thread panel, a per-survey
  list of open threads with counts on the Structure pane. Responses map: thread on a
  single answer's popup.
- **Email notification is part of the MVP, not a follow-up.** Clients live in their inbox,
  not in the product; without "Artem replied on question 3" plus a deep link the feature
  is dead on arrival. Reply-by-email is out of scope for v1.
- Permissions: every workspace member reads and writes; read-only guests (once
  [#91](feature-workspace-roles-permissions.md) exists) can comment but not resolve.
- Sanitize bodies through `survey/html_sanitize.py` like every other creator-written
  field, or keep them plain text and escape on render.

## Later

- A thread on a question saying "make this required" becomes a command for the AI editor
  agent, which applies the edit and asks the owner to confirm. Separate change; threads
  first.
- Suggestion mode (proposed text edit, owner accepts/rejects) — only if the comment
  volume shows people asking for it.

## Notes

Promoted on 2026-09-15 — worktree `Mapsurvey-comment-threads`, branch `feature/survey-comment-threads`.
Implemented 2026-09-15 in `openspec/changes/survey-comment-threads/` (one PR: all four anchors, drawer, mail, attachments).

`CreatorNote` is unrelated: those are our internal CRM notes about a creator, invisible to
them. Nothing comment-like exists in the codebase today.
