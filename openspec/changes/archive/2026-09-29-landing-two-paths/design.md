## Context

The landing page (`survey/templates/landing.html` on `base_landing.html`, styles in `survey/assets/css/landing.css`) ends in two call-to-action blocks: `.mid-cta` ("Ready to create your own?") and `.final-cta` (Discord + GitHub). Discord is also in the hero, on `/for-educators/` and in the footer; `/services/` books calls through `mailto:`. A Cal.com booking page now exists. Approved mockup: `how-to-start.mockup.html`.

## Goals / Non-Goals

**Goals:** answer "what next?" with two explicit paths; one button per block; nothing on the page we cannot back.

**Non-Goals:** customer logos or quotes (waiting for permissions), a price on the page (#157), the EU claims on other landing templates (#191), redesigning the rest of the page.

## Decisions

- **One setting, `BOOK_A_CALL_URL`**, read in `survey/context_processors.contact` next to the other landing links; env var with the Cal.com URL as default so previews and local dev render the same buttons as production. Swapping the booking tool is an env change, not a deploy.
- **Remove `DISCORD_INVITE_URL` outright** rather than leaving it dormant: a setting nothing reads invites someone to wire it back in.
- **Replace `.mid-cta` and `.final-cta` with one `.how-to-start` section** at the end of the page. Both old blocks only repeated "Create", so merging them removes a duplicate CTA instead of adding a third.
- **"With us" card falls back to `/services/`** when the setting is empty, so the card never renders a dead button.
- **Visual weight**: the "yourself" button stays teal (`btn-primary-landing`); the "with us" button uses the primary slate so the two paths read as equals, not primary/secondary. Cards stack below 760px, "yourself" first, since most visitors on phones are respondents' peers and students, not buyers.
- **Government card copy** loses "stays on your infrastructure", "no annual subscription" (Pro is $490/yr) and the GDPR line; it now leans on what is true: no GIS team, open source, export to GeoJSON / Excel / Shapefile.
- **`book_call_clicked`** fires from one small delegated listener on `[data-book-call]` in `base_landing.html`, guarded by `window.posthog`, carrying only `surface` (`hero`, `how_to_start`, `footer`, `services`, `educators`). No slug or URL, as with the other creator events.

## Risks / Trade-offs

- [The Cal.com username changes again] → the URL is one env var; the default in `settings.py` is the only other place.
- [Removing the demo button from the hero lowers demo opens] → it stays as a text link; demo opens are tracked in `DemoOpen`, so a drop is visible in the funnel dashboard.

## Migration Plan

Template/CSS/settings only; no migrations. Rollback = revert the PR.
