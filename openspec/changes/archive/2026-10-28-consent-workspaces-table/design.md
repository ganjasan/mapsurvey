## Context

`AuthorizeView.get_context_data` builds `workspaces` (name, plan, api) ordered by name;
`authorize.html` prints them inline. The page has no script and should not need one.

## Goals / Non-Goals

**Goals:** a short page with *Allow* in view; the Pro workspaces easy to spot.
**Non-Goals:** choosing which workspaces the grant reaches (it reaches every membership, as before).

## Decisions

### D1 · Native `<details>`, closed by default
No JavaScript, keyboard- and screen-reader-accessible, works inside the strict CSP the `/oauth/*`
responses carry. The summary carries the information a quick reader needs (count, how many on Pro),
so closed is the right default.

### D2 · Order and counts in the view
`api` first, then name (case-insensitive) — sorted in Python next to the existing loop; the template
only draws. `pro_count` joins `any_pro` in the context.

## Risks / Trade-offs

- [A reader never opens the table] → The summary already says how many workspaces the app reaches and how many can use it.
