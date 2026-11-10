## Why

Chrome around the first survey pushes new creators off the onboarding flow (#638). The app
sidebar hangs a Pro mark on Sites, API, MCP and Map styles; on a Free workspace the sidebar hides
the mark's "· free to try", so a filled violet "★ PRO" reads as "paid, not for you" — while the
first use of any of them would start the free trial by itself. On a Pro workspace the same marks
tell a paying creator nothing. Every editor page of a new account carries a yellow "Confirm your
email address… you can sign in for N hours more" strip. The start page offers a third path
(*Use your AI assistant*) next to the two that actually make a survey, and the expanded sidebar
offers a dozen more places to go before there is a survey to work on. Meanwhile the support chat
— the one thing that helps a stuck creator — has no visible entry on the editor besides the "?"
menu.

## What Changes

- Sidebar items carry no Pro mark while the feature is in the plan, in a live trial, or would
  start the trial on first use. A workspace that can no longer use it (`locked`) gets a small grey
  lock without the word "Pro". The mark comes from a new registry tag `{% pro_nav_mark org "key" %}`.
  Point-of-use `{% pro_badge %}` marks are unchanged.
- The confirm-your-email banner strip is removed from every editor page and the dashboard. The
  "Confirm your email to publish" dialog and its resend script stay.
- The start page loses the *Use your AI assistant* card: two cards, Wizard and From scratch. The
  agent page stays reachable from the sidebar's *MCP* item, the "?" menu and the help centre.
- While the active workspace has no surveys, workspace-level pages open the sidebar as the rail;
  an explicit *Expand* wins and is remembered as before.
- The Chatwoot bubble shows on editor pages on a desktop (never on a phone), with a "×" that hides
  it in that browser and a "Show chat button" item in the "?" menu that brings it back. The editor
  widget still never opens an unread pop-up.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `workspace-navigation`: no Pro mark on sidebar items (a lock only when locked); the rail by default before the first survey.
- `plan-entitlements`: adds the navigation variant of the Pro mark (`pro_nav_mark`).
- `sign-in-grace-period`: the editor no longer shows the confirm-email banner; the reminder lives in the publish dialog.
- `survey-start-chooser`: two cards; the assistant card is removed.
- `agent-access-teaser`: the start page is no longer an entrance to the agent page.
- `support-chat`: the editor shows the bubble on a desktop, hideable by the creator; never on a phone.

## Impact

- `billing/templatetags/billing_tags.py`, new `billing/templates/billing/_pro_nav_mark.html`,
  `css/pro_badge.css`, `css/app_sidebar.css`.
- `survey/templates/partials/_app_sidebar.html`, `survey/context_processors.py` (`app_nav.onboarding`,
  `support_chat.hide_label`, `email_verification`).
- `survey/templates/editor/partials/_confirm_email_banner.html`, `editor/survey_start.html`,
  `partials/_support_chat.html`, `editor/partials/_help_menu.html`, `base.html`, `editor/editor_base.html`.
- Catalogs: two new msgids in the offered languages + ru.
- Help centre pages that describe the start page's third card.
- No model, URL or API change. Rollback = revert.
