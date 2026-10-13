# Support Chat Specification

## Purpose
The in-product support chat (Chatwoot): where the widget loads, when it is off, how signed-in creators are identified and reset, where the help entry point lives on working surfaces, and what context the agent receives.
## Requirements
### Requirement: Support chat widget is Chatwoot
Pages built on `base_landing.html`, `base.html` and `editor/editor_base.html` SHALL load the Chatwoot web widget from `CHATWOOT_BASE_URL` with `CHATWOOT_WEBSITE_TOKEN`, rendered from a single shared partial. The tawk.to widget SHALL NOT be loaded.

#### Scenario: Configured widget loads
- **WHEN** `CHATWOOT_WEBSITE_TOKEN` is set and any of the three base templates is rendered
- **THEN** the page includes the Chatwoot SDK from `CHATWOOT_BASE_URL` and runs it with the website token

#### Scenario: tawk.to is gone
- **WHEN** any page is rendered
- **THEN** the HTML SHALL NOT reference `embed.tawk.to`

#### Scenario: Unconfigured widget is off
- **WHEN** `CHATWOOT_WEBSITE_TOKEN` is empty
- **THEN** the page SHALL NOT include the Chatwoot SDK, and `openSupportChat` exists and does nothing

### Requirement: Signed-in creators are identified
For an authenticated user the widget SHALL be told the user's identifier (`str(user.pk)`), email and display name. When `CHATWOOT_HMAC_TOKEN` is set, it SHALL also be given `identifier_hash = HMAC-SHA256(key=CHATWOOT_HMAC_TOKEN, message=identifier)` as lowercase hex, computed on the server. The HMAC token SHALL NOT appear in the HTML.

#### Scenario: Signed-in user with HMAC token
- **WHEN** an authenticated user renders a page and `CHATWOOT_HMAC_TOKEN` is set
- **THEN** the page passes identifier, email, name and the matching `identifier_hash` to the widget, and the token itself is absent from the HTML

#### Scenario: Signed-in user without HMAC token
- **WHEN** an authenticated user renders a page and `CHATWOOT_HMAC_TOKEN` is empty
- **THEN** the page passes identifier, email and name without `identifier_hash`

#### Scenario: Anonymous visitor
- **WHEN** an anonymous visitor renders a page
- **THEN** the page passes no user identity to the widget

### Requirement: Session reset after sign-out
A page rendered for an anonymous visitor in a browser where the widget previously identified a user SHALL reset the Chatwoot session, so the next visitor does not see the previous user's conversation.

#### Scenario: Visitor after logout
- **WHEN** a browser that identified a user to the widget renders a page without a signed-in user
- **THEN** the widget session is reset once and the identification marker is cleared

### Requirement: Bubble placement follows the editor navigation flag
With `MOBILE_EDITOR_NAV` on, `base.html` and `editor/editor_base.html` SHALL hide the floating chat bubble and open the chat only through `openSupportChat`. Otherwise, and always on `base_landing.html`, the bubble SHALL be shown.

#### Scenario: Working surface under MOBILE_EDITOR_NAV
- **WHEN** `MOBILE_EDITOR_NAV` is on and an editor page is rendered
- **THEN** the widget is configured with the message bubble hidden, and "Help & support" opens the chat

#### Scenario: Landing page
- **WHEN** the landing page is rendered
- **THEN** the widget is configured with the message bubble shown

### Requirement: Widget language follows the page
The widget SHALL be configured with the page's active language code.

#### Scenario: Russian landing
- **WHEN** a page is rendered with active language `ru`
- **THEN** the widget is configured with locale `ru`

### Requirement: Help entry point in the editor header
Pages built on `base.html` and `editor/editor_base.html` SHALL show a "?" help control in the header for signed-in creators (desktop widths; phones keep "Help & support" in the ⋯ and account menus). It SHALL open a menu — "What's new", "Help centre", then "Help & support" with a line setting the reply expectation — rather than the chat itself. "Help centre" SHALL link to the help site home from the help-links registry (`HELP_URL.help_home`) and open in a new tab; when `HELP_SITE_URL` is empty the item SHALL be omitted. When the chat is unconfigured the menu SHALL offer `mailto:CONTACT_EMAIL` instead of "Help & support".

#### Scenario: Configured chat
- **WHEN** a signed-in creator opens an editor page and `CHATWOOT_WEBSITE_TOKEN` is set
- **THEN** the header carries the "?" menu with "Help & support" calling `openSupportChat` and the reply-expectation line

#### Scenario: Unconfigured chat
- **WHEN** a signed-in creator opens an editor page and `CHATWOOT_WEBSITE_TOKEN` is empty
- **THEN** the "?" menu offers an email link to `CONTACT_EMAIL` and no chat entry

#### Scenario: Help centre link
- **WHEN** a signed-in creator opens an editor page and `HELP_SITE_URL` is set
- **THEN** the "?" menu carries "Help centre" linking to `HELP_SITE_URL` with `target="_blank"` and `rel="noopener"`, and no link to `#faq` is rendered

#### Scenario: Help site disabled
- **WHEN** `HELP_SITE_URL` is empty
- **THEN** the "?" menu shows "What's new" and the support entry only

### Requirement: The hidden widget never speaks first
With the bubble hidden, the widget SHALL NOT show its unread-messages pop-up or pop-out button. A reply received while the chat is closed SHALL be signalled only by an unread dot on the help entry points, cleared when the chat opens.

#### Scenario: Agent reply while the chat is closed
- **WHEN** the widget reports an unread count above zero on a page with the bubble hidden
- **THEN** every `.support-unread` marker is shown, and hidden again once the chat is opened

### Requirement: Conversation context for the agent
For a signed-in creator the widget SHALL be given custom attributes: workspace slug, plan, current page path and, when the URL names one, the survey UUID. `openSupportChat(event, context)` SHALL merge `context` into those attributes before opening the chat.

#### Scenario: Editor page in a workspace
- **WHEN** a signed-in creator with an active workspace on the free plan renders an editor page
- **THEN** the page passes `workspace` and `plan: free` to the widget, and the browser adds `page` and `survey`
