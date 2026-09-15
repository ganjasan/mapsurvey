# Epic: Team Collaboration

**Description**: Everything that lets more than one person work on a survey inside one
workspace — discussing it, proposing changes, controlling who may edit what, and being
told by email when something needs them. The target pair is a client's project owner
plus us finishing the survey for them; the second pair is a consultancy plus the
municipality that commissioned the study.

**Created**: 2026-09-15

## Why an epic

Prod on 2026-09-15: 374 of 391 workspaces have one member, 17 have two or three — and
those 17 are the top leads (Decisio, SPEN, BMP2026, City of Olney). In every one of them
the pattern is the same: we sit inside the client's workspace and finish the survey
(memory `project_service_model_hypothesis`). Today that work runs over email, and the
context — which question a note referred to — is lost within a week. These items are the
working surface for the service we already deliver by hand.

## Items

| Item | Ref | Role in the epic |
|------|-----|------------------|
| Comment threads anchored to survey objects | [#169](../feature-survey-comment-threads.md) | The working surface: discuss a question, a section, a results block or a single answer where it lives, resolve, get the reply by email |
| Workspace roles & permissions, incl. read-only client access | [#91](../feature-workspace-roles-permissions.md) | Who may edit, who may only comment, who only watches — the municipality watching a consultancy's collection |

## Later

- A thread on a question ("make this required") becomes a command for the AI editor
  agent, applied and offered to the owner for confirmation.
- Suggestion mode: proposed text edit, owner accepts or rejects.
- Reply-by-email into a thread.

## Sequencing

#169 first: it is useful with today's flat membership and it is what City of Olney needs
in September. #91 second, and it should land before the first paid client-plus-consultancy
pair, because that is where "the client can see but not edit" is the purchase trigger.
Both stay Pro-tier features commercially; the epic is about the work, the tier is about
the price.
