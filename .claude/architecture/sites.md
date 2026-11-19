# Sites (/p/<slug>/)

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Sites (`/p/<slug>/`, epic #348; called "Landing pages" until 2026-11-09)**: a workspace's public
site for an engagement — a landscape/planning firm's project site or a council's — built from a
CLOSED set of blocks (`survey/sites.py::BLOCK_KINDS`, one cleaner per kind in `clean_block`, one
public template `sites/blocks/<kind>.html`, one canvas include). Models `Site`, `SiteSurvey`
(surveys linked many-to-many), `SiteBlock`, `SiteFile`, `EventRegistration`; Pro feature `sites`
(trial: one site), a published site survives a lapse. The builder (`site_views.py`,
`templates/sites/builder.html`, `js/site_builder.js`) is the page as visitors see it: the panel form
(`sites/_block_form.html`) is the ONE serialisation of a block, canvas edits travel in its hidden
fields, every change autosaves with `autosave=1` (JSON fragments; an EMPTY field waits, a wrong value
is a 422). Owner rules: a block's primary actions happen in the block, refinements in Settings; reuse
the app's dialogs and toolbars (no `confirm()`). **Every write goes through `survey/services/sites.py`**
(change `sites-service-layer`, #617) — `SiteServiceLayerTest` fails if a view writes a row itself.
Never name a template context variable `block` in a template extending a base (it is a `BlockNode`);
the builder uses `b`/`edit_block`. CSS prefixes `lp-` (public) / `lb-` (builder) are historical
internal names; the marketing `css/landing.css` and the SEO landings are a different thing. Plan of
the next waves: ops `requirements/design/sites-v1.1-architecture-and-plan.md`.
