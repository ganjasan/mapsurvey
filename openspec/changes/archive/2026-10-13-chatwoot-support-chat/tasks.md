## 1. Settings

- [x] 1.1 Add `CHATWOOT_BASE_URL` (default `https://app.chatwoot.com`), `CHATWOOT_WEBSITE_TOKEN`, `CHATWOOT_HMAC_TOKEN` to `mapsurvey/settings.py`
- [x] 1.2 Declare the three keys in `render.yaml` (web service, `sync: false` for tokens)

## 2. Server side

- [x] 2.1 `support_chat` context processor: config + signed-in identity with `identifier_hash`
- [x] 2.2 Register the processor in `TEMPLATES`

## 3. Templates

- [x] 3.1 Partial `partials/_support_chat.html`: settings, SDK loader, `setUser` on `chatwoot:ready`, reset after sign-out, `openSupportChat`
- [x] 3.2 Replace the tawk.to snippet in `base_landing.html`, `base.html`, `editor/editor_base.html` with the include (bubble hidden under `MOBILE_EDITOR_NAV` except on landing)

## 4. Tests

- [x] 4.1 Context processor tests (GIVEN/WHEN/THEN): signed-in with/without HMAC token, anonymous, unconfigured
- [x] 4.2 Template tests: no `embed.tawk.to`; SDK present only when configured; token absent from HTML; bubble flag on landing vs editor

## 5. Help entry point (owner decision after 5.1: no bubble on working surfaces, but help must be findable)

- [x] 5.1 `editor/partials/_help_menu.html`: "?" dropdown (What's new, FAQ, Help & support + expectation line; mailto fallback) in `base.html` and `editor_base.html`
- [x] 5.2 Unread dot on the entry points from the widget's `handleNotificationDot` message; unread pop-up and pop-out off when the bubble is hidden
- [x] 5.3 Custom attributes (workspace, plan, page, survey) and the `openSupportChat(event, context)` hook for #295
- [x] 5.4 Tests for 5.1–5.3

## 6. Verification

- [x] 5.1 Local dev server with the real website token: signed-in chat shows a verified contact in Chatwoot
- [ ] 6.2 Reply after the tab is closed arrives by email
