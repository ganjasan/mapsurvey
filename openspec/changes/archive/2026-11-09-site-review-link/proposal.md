## Why

Issue #608 (epic #348, Sites v1.1 wave A, story S11). A consultancy shows the client the site before it goes live; the client is not a member of the workspace, and today only members can open a draft.

## What Changes

- **Share for review** in the Publish popover of an unpublished site: a link `/p/<slug>/?review=<token>` that opens the draft read-only for anyone, for 14 days, with a "Shared for review — this site is not public yet" banner, `noindex`, `no-store` and `Referrer-Policy: no-referrer`.
- In review mode event registration is replaced by "Registration opens when the site is published"; the report link is hidden.
- **New link** (owner, admin, editor) rotates `Site.review_salt`; every link handed out before stops working.
- A site held for a safety review never opens through a review link; a published site needs none.

## Capabilities

### Modified Capabilities
- `survey-sites`: a draft can be shared for review without an account.

## Impact

Migration `0124_site_review_link` (`review_salt`, additive with `db_default`), `sites.py` (signer helpers), `site_views.py` (`site_public`, `editor_site_review_link`), URL, `public.html`, `blocks/event.html`, `builder.html`, CSS, JS, help, catalogs.
