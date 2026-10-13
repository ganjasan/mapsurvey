## Context

The tawk.to snippet is copy-pasted into three base templates. `base.html` and `editor/editor_base.html` carry a `MOBILE_EDITOR_NAV` variant: no floating bubble, `window.openSupportChat(e)` opens the chat from "Help & support" menu items (`base.html`, `editor.html`, `editor/editor_base.html`). `base_landing.html` shows the bubble. tawk.to receives no user identity, so an unanswered chat cannot be followed up (#291).

Chatwoot Cloud account 191279 is on the free plan. Its Website inbox (146110) has `continuity_via_email` on and an HMAC token; the API access token is paid, so the inbox is configured in the dashboard by hand.

## Goals / Non-Goals

**Goals:**
- One support-chat partial, included by the three base templates.
- Signed-in creators arrive in Chatwoot as verified contacts (id, email, name).
- Same UX as today: bubble hidden under `MOBILE_EDITOR_NAV`, "Help & support" opens the chat.
- No widget, no third-party request when unconfigured.

**Non-Goals:**
- Provisioning Chatwoot through its API (paid).
- Changing where the widget appears. Respondent-facing pages that extend `base.html` (`survey_thanks`, `survey_password`, `survey_closed`, …) carry the widget today and keep it; narrowing that is a separate decision.
- A Chatwoot MCP / API integration for triaging conversations.

## Decisions

**Identifier is `str(user.pk)`, not the email.** Email is editable; a contact keyed by email would split when it changes. Same reasoning as `_posthog_person`. Email and name are sent as attributes and updated on each page load.

**`identifier_hash` is computed in the context processor** with `hmac.new(CHATWOOT_HMAC_TOKEN, identifier, sha256).hexdigest()`. The token stays server-side. Without the token the processor still sends identifier/email/name unsigned — Chatwoot accepts that because "Require identity validation for all conversations" stays OFF for good: with it on, Chatwoot rejects every conversation without a valid token, which would shut out anonymous landing visitors. With it off, a signed contact shows as verified and an unsigned or forged one carries Chatwoot's "not verified" warning — enough for the agent to judge.

**A page for a different visitor drops the old Chatwoot session before the SDK starts.** Logout is a plain link, so there is no JS hook at the moment of logout. The partial remembers the last identifier in `localStorage['ms_support_chat_identifier']`; a page rendered for nobody or for another user that finds a different value deletes Chatwoot's own first-party cookies (`cw_conversation`, `cw_user_<website token>`) before loading the SDK. Not `$chatwoot.reset()`: the SDK source shows it reloads the widget frame without a second `chatwoot:ready`, and its `setUser` dedupes on a cookie fingerprint, so a `setUser` right after a reset can be lost for good. Alternative — hooking the logout links — misses session expiry and logout from another tab.

**Bubble hiding via `chatwootSettings.hideMessageBubble`.** Chatwoot reads it before rendering, so there is no bubble flash (the reason tawk.to needed `autoStart=false`). `openSupportChat()` calls `$chatwoot.toggle('open')`, waiting for `chatwoot:ready` if the SDK has not finished loading.

**"?" help menu instead of a direct chat link (owner decision, 2026-10-13).** The bubble stays hidden on working surfaces, but "Help & support" buried in two overflow menus is not findable by someone whose save just failed. NN/g: help must not interfere and must be easy to find. So: one "?" in the header (the convention of Notion/Figma/Linear), opening a menu with self-service first (What's new, FAQ) and the chat last, plus one line setting the reply expectation. The widget never speaks first there — `showUnreadMessagesDialog` and `showPopoutButton` off; an agent reply is an unread dot on the entry points, driven by the same `handleNotificationDot` postMessage the SDK uses for its bubble dot (the SDK skips the dot when the bubble is hidden). Context for the agent (workspace, plan, page, survey) goes through `setCustomAttributes` — CONTACT attributes, verified to land on the contact in Chatwoot Cloud; `page` is therefore "last page seen", which is what the agent needs. Conversation attributes (`setConversationCustomAttributes`) were not used: the widget only applies them once a conversation exists. The dashboard shows a custom attribute only when a definition with that key exists (Settings → Custom Attributes), so `workspace`, `plan`, `page`, `survey` need contact-type definitions there — a manual step, API tokens being paid; `openSupportChat(event, context)` is the hook for help at the point of failure (#295, separate change).

**Widget locale follows the page** (`{% get_current_language %}`), so the RU landing gets a Russian widget.

**Settings are environment variables**, `sync: false` in `render.yaml`, values on the service and in `mapsurvey-shared` (previews). `CHATWOOT_BASE_URL` defaults to `https://app.chatwoot.com`.

## Risks / Trade-offs

- [Free plan limits: 2 agents, 500 conversations/month, 30-day retention] → current support volume is far below; revisit if the limit is hit.
- [Enforcement off: a visitor can claim another email from the console] → such a contact is flagged "not verified" in Chatwoot; agents reply by email only to verified contacts.
- ["Allowed Domains" empty: the widget token works on any site] → set to the production and preview hosts after the deploy is verified.
- [Third-party script on respondent pages] → unchanged from tawk.to; noted as a non-goal.
- [Chatwoot outage] → the page does not depend on the SDK; `openSupportChat` gives up silently after the wait, as today.

## Migration Plan

1. Deploy with `CHATWOOT_WEBSITE_TOKEN` + `CHATWOOT_HMAC_TOKEN` set on production and in `mapsurvey-shared`.
2. Verify: signed-in chat shows a verified contact; reply to a closed tab arrives by email.
3. Set the inbox's "Allowed Domains" to the production and preview hosts. Leave "Require identity validation" off (anonymous landing visitors). Set the inbox reply time to "in a day" (the help menu promises a day). Add contact custom-attribute definitions `workspace`, `plan`, `page`, `survey` so they show in the sidebar.
4. Remove the tawk.to property.

Rollback: unset `CHATWOOT_WEBSITE_TOKEN` (widget disappears) or revert the PR.

## Open Questions

- Should respondent-facing pages keep a support widget at all?
