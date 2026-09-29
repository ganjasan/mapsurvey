## Why

The landing page answers "do you do the job I need?" well, but not "what next?" for half of its audience. The only path it offers is "register and build it yourself"; a council, agency or consultancy for whom a survey is a line in a project budget leaves without a next step, because the done-with-you offer on `/services/` is reachable only through the menu. The page also still pushes Discord (nobody uses it; the owner retired it on 2026-09-29) and carries two claims we cannot back while hosting is in Oregon: a "GDPR-Friendly" hero badge and "Citizen data stays on your infrastructure" on the government card.

A booking page now exists (Cal.com, `https://cal.com/mapsurvey-artem/mapsurvey-call`), so the "with us" path can end in a real calendar slot instead of a mailto.

## What Changes

- New **"How to start"** block with two paths side by side, replacing the mid-page "Ready to create your own?" block and the final Discord/GitHub block (mockup: `how-to-start.mockup.html`):
  - *Build it yourself* — free, AI draft, publish and share; one CTA: Create your Mapsurvey.
  - *Build it with us* — 30-minute call, fixed quote, response target; one CTA: Book a 30-min call, plus a text link to `/services/`.
- **Hero**: Discord button → "Book a 30-min call"; the demo survey becomes a text link under the buttons so the hero has two buttons, not three. "GDPR-Friendly" badge → "You own the data".
- **Government use-case card**: drop "stays on your infrastructure" and the GDPR/data-sovereignty compliance line; keep "no vendor lock-in, open source".
- **Footer** (`base_landing.html`): Discord link → "Book a call".
- **For educators** page: Discord button → "Book a call".
- **Services** page: both "Book a short call" buttons go to the booking page instead of `mailto:`.
- New setting `BOOK_A_CALL_URL` (env, default the Cal.com URL) exposed through the context processor, same pattern as `DISCORD_INVITE_URL`. Every Book-a-call button renders only when it is set.
- `DISCORD_INVITE_URL` is no longer rendered anywhere; the setting and context key are removed.

Out of scope: the "who already uses Mapsurvey" block (waits for publication permissions, asked 2026-09-29), a visible price (#157), hiding the empty Stories link, and the EU-hosting claims on the other landing templates (#191).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `landing-page`: the hero's CTAs change (register + book a call, demo as a link); a new "How to start" section with the two paths is required; the footer offers Book a call instead of a community link; Book-a-call targets come from `BOOK_A_CALL_URL`. The stale "Order a Survey" / Telegram / contact-section requirements are replaced by what the page actually does.

## Impact

- Templates: `survey/templates/landing.html`, `base_landing.html`, `for_educators.html`, `services.html`.
- CSS: `survey/assets/css/landing.css` (new `.how-to-start` / `.path` rules; `.mid-cta` and `.final-cta` rules go if nothing else uses them), then `collectstatic`.
- Settings / context: `mapsurvey/settings.py`, `survey/context_processors.py`; Render env gets `BOOK_A_CALL_URL` only if it must differ from the default.
- i18n: new and changed `{% trans %}` strings → `ru` catalog.
- Tests: landing render tests that assert Discord markup or the old CTA blocks.
- Analytics: the Book-a-call click is worth a PostHog event (`book_call_clicked`, with the surface), browser-side and guarded by `window.posthog`, like `share_link_copied`.
