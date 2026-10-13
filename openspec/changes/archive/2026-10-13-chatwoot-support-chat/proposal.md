## Why

Support runs on tawk.to, which identifies a visitor only by browser cookie: no email, no account, no persistent conversation. A question not answered while the creator is still on the page is lost — there is no channel to reply later (issue #291). Chatwoot keeps one conversation per identified user and delivers replies to offline users by email, and its Cloud "Hacker" plan is free.

## What Changes

- Replace the tawk.to widget with the Chatwoot web widget on every page that carries it today (`base_landing.html`, `base.html`, `editor/editor_base.html`).
- Extract the duplicated snippet into a single partial `partials/_support_chat.html`; the three base templates include it.
- Signed-in creators are identified: `identifier = user.pk`, plus `email` and `name`, signed with `identifier_hash = HMAC-SHA256(identifier, CHATWOOT_HMAC_TOKEN)` computed server-side. The HMAC token never reaches the browser.
- A page rendered for an anonymous visitor after a signed-in one in the same browser resets the Chatwoot session, so the next visitor does not inherit the previous creator's conversation.
- Keep the current UX contract: under `MOBILE_EDITOR_NAV` there is no floating bubble and "Help & support" opens the chat; otherwise the bubble is shown.
- The widget is off (nothing rendered, no third-party request) when `CHATWOOT_WEBSITE_TOKEN` is unset. Identification is off when `CHATWOOT_HMAC_TOKEN` is unset.
- **BREAKING** (ops): tawk.to is removed; its property stops receiving chats once deployed.

## Capabilities

### New Capabilities
- `support-chat`: the in-product support chat widget — where it loads, when it is off, how signed-in users are identified and how the session is reset.

### Modified Capabilities
<!-- none: no existing spec covers the support widget -->

## Impact

- Templates: `survey/templates/base_landing.html`, `survey/templates/base.html`, `survey/templates/editor/editor_base.html`; new `survey/templates/partials/_support_chat.html`.
- `survey/context_processors.py`: new `support_chat` processor; registered in `mapsurvey/settings.py`.
- Settings / env: `CHATWOOT_BASE_URL` (default `https://app.chatwoot.com`), `CHATWOOT_WEBSITE_TOKEN`, `CHATWOOT_HMAC_TOKEN`; `render.yaml` declares them `sync: false`; values go to the service and the `mapsurvey-shared` env group.
- Third party: browser loads `https://app.chatwoot.com/packs/js/sdk.js` instead of `embed.tawk.to`.
- Ops: Chatwoot Cloud account 191279 (free "Hacker" plan), Website inbox "Mapsurvey" (id 146110) already created by hand — the Chatwoot API token is a paid feature, so configuration stays manual. The inbox has conversation continuity via email on and an HMAC token; "Require identity validation for all conversations" stays off so anonymous landing visitors can still chat.
