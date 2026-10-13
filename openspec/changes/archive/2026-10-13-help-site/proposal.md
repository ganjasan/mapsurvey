## Why

Creators have nowhere to read how Mapsurvey works: the editor Help menu points at `/#faq`, an anchor the homepage does not have, and the only FAQ content is the "why Mapsurvey" block on the SEO landings. Support is self-service first (support-chat spec, #291), so the Help entry must lead to answers about tasks — first survey, reference layers, exports, embedding, Pro, MCP — before it leads to a human (issue #298). Our audience (planners, consultants, researchers, educators) also lacks a place that teaches the craft itself: how to design a participatory mapping survey, what the PPGIS research says will go wrong, how to read the results. Nobody in the market owns that ground.

## What Changes

- A help site at **help.mapsurvey.org**: a Starlight (Astro) project in `help/` of this repository, deployed as a Render static site built from that folder.
- Sections follow Diátaxis (documentation split by what the reader is doing, not by topic):
  - **Start here** — one tutorial: build, publish and read a first survey end to end.
  - **How-to guides** — one task per page, action titles ("Add a reference layer"), numbered steps, no theory.
  - **Reference** — question types, answer formats, export columns, survey settings, MCP tools.
  - **Troubleshooting** — symptom → cause → fix pages with stable URLs, the target of "Contact support at the point of failure" links (#295).
  - **Learn** — citizen engagement and participatory mapping as a practice, not as a product feature: designing a map survey, question design rules and their evidence, recruiting respondents and bias, reading and presenting spatial answers, privacy and ethics. Seeded from `docs/research/survey-design-rules.md` (the tracked PPGIS design-rules document) and the public stories.
  - **Use cases** — one page per real survey: what was asked, how it was built, what came back, linking the public story.
  - **FAQ** — short answers (≤ 3 sentences) to questions people actually asked, each linking to the page that answers in full; grouped, jump links, no accordions on desktop.
- FAQ governance: the seed comes from the landing FAQs and the tawk.to / Chatwoot history; from then on a closed support conversation either adds an FAQ entry or fixes a guide. Invented questions are out.
- Site-wide search (Pagefind, built at deploy, no server) and an i18n-ready layout: English is the root locale served without a prefix; other creator UI languages are added as folders, with fallback to English.
- Every page ends with "Was this helpful?" and a "Still stuck? Contact support" block (chat on the main site, email otherwise). Page feedback and search terms are recorded in PostHog so the FAQ and guides are maintained from evidence.
- The editor Help menu item "FAQ" becomes "Help centre" and opens the help site in a new tab; the dead `#faq` link goes away.
- "Learn more" links from editor surfaces to specific pages (reference layers, embedding, Pro, exports). Product-side links go through one registry so a test can prove every linked page exists.
- The help site is a public, indexable property: `robots.txt`, sitemap, canonical URLs, `hreflang` between locales; preview deploys are `noindex`. The main site's sitemap and landing FAQs stay as they are.
- No preview environments for the help site (owner decision): guides are reviewed locally with `npm run dev` and go to production on merge.
- An authoring guide (`help/CONTRIBUTING.md`): page types, title and heading rules, screenshot conventions, where a new page goes.

Not in this change: translating the content; FAQPage structured data (Google shows FAQ rich results only to government and health sites since August 2023); moving `docs/OVERVIEW.md` or marketing notes; a Chatwoot Help Center portal; in-editor contextual help beyond links; the local `docs/use_cases/` idea notes, which are untracked product research and not user-facing.

## Capabilities

### New Capabilities
- `help-site`: the public help site — information architecture (Start here, How-to, Reference, Troubleshooting, Learn, FAQ), page conventions, search, locale layout, feedback and analytics, deployment as a Render static site from `help/`, and how the product links into it.

### Modified Capabilities
- `support-chat`: the "Help entry point in the editor header" requirement changes — the menu item "FAQ" (`/#faq`) becomes "Help centre" opening the help site.
- `render-deployment`: a new static-site service built from `help/` joins the Blueprint, without preview environments.

## Impact

- New: `help/` (Astro + Starlight project with its own `package.json`, content in `help/src/content/docs/`, `help/CONTRIBUTING.md`), Render static service `mapsurvey-help` in `render.yaml` (`rootDir: help`, build filter on `help/**`), custom domain `help.mapsurvey.org` (DNS CNAME, added by hand in the Render dashboard), PostHog project property for the help site.
- Changed: `survey/templates/editor/partials/_help_menu.html` (menu item and URL); `mapsurvey/settings.py` gets `HELP_SITE_URL` (default `https://help.mapsurvey.org`) exposed through a context processor; a small `survey/help_links.py` registry; editor templates that gain "Learn more" links; `survey/tests.py` for the help-menu and registry assertions.
- Content sources: `docs/research/survey-design-rules.md` stays the canonical rules file (it feeds the AI draft prompt and the `newsurvey` skill); Learn pages are written from it and link back. Private research notes in `../Mapsurvey-ops` may be paraphrased, never copied; no third-party PDFs are published.
- Build: Node is needed only for the static service; the Django Docker image and test suite are untouched. No new Python dependencies.
- Ops: one more Render service (static sites and their previews are free), one DNS record. Search is a build-time index; no third-party search service.
