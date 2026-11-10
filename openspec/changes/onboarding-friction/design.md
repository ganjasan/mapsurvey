## Context

`{% pro_badge %}` (change pro-trial-auto, #508) has four states and is used at points of use and
in the app sidebar (change app-sidebar). The sidebar hides `.pro-badge__extra` for lack of room,
which strips "free to try" / "N left" and leaves a bare "PRO" in every state. The confirm-email
partial (change login-grace-period, #487) holds three things: the banner strip, the publish
refusal dialog, and the resend script both share.

## Goals / Non-Goals

**Goals:** no Pro wording in navigation unless the feature is out of reach; no standing
confirm-email strip; the publish dialog and resend behave exactly as before.

**Non-Goals:** changing point-of-use marks, the trial rules, the grace period length, the
sign-in refusal after the deadline, or the invitation refusal.

## Decisions

- **A second tag, `pro_nav_mark`, over a `nav=True` flag on `pro_badge`.** Navigation and
  controls answer different questions (can I get there vs. what will this use cost), and a
  separate tag keeps `_pro_badge.html` and its four-state contract untouched. Both share
  `pro_badge_state`, so they cannot disagree on the state.
- **Locked keeps a lock.** A creator who can no longer use the feature should not be surprised on
  the page; the lock is the least wording that says so. Its tooltip is the `pro_badge` locked one,
  so no new msgid.
- **Banner: delete the markup and its CSS, keep the partial and its include points.** The dialog
  and script still render only for an unconfirmed account (`email_confirmation`), so both bases
  keep including the partial. The script's `closest('.ms-confirm-email, …')` becomes
  `closest('.modal-content')`; the `.ms-confirm-email__status` class on the dialog keeps its rule.
- Orphaned msgids ("Confirm your email address.", the countdown sentence) are left in the catalogs;
  `makemessages` is not run in this project and an unused entry is harmless.

## Risks / Trade-offs

- [An unconfirmed creator is signed out at the 24-hour mark without warning] → the session ends on
  the next request, and the sign-in form, given the correct password, explains it and sends a link
  itself; most onboarding happens in the first session.
- [Free creators click Sites/Map styles and meet a Pro offer on the page] → that is the intent:
  the first use starts the trial, and the page says so in full.

## Migration Plan

Template and CSS only; deploy and revert are plain.

## Additions (same change, after review on the dev stand)

- **Start page: two cards.** The agent card is removed rather than demoted: the owner wants nothing
  on the first screen that does not make a survey. The page narrows to 860 px so two cards do not
  stretch. The agent page keeps its three entrances (sidebar *MCP*, "?" menu, help centre).
- **Onboarding rail = "the active workspace has no surveys"**, the same test as the dashboard's
  redirect to the start page, for owner/admin/editor only. Rendered as a flag into the sidebar's
  inline before-paint script, so no flash; `localStorage['msSidebar'] === 'wide'` (an explicit
  Expand) wins, and Expand on such a page is remembered by the existing toggle code. An invitee
  joining a workspace with surveys never sees the rail by default.
- **Chat bubble: per browser, not per account.** `localStorage['msSupportBubble']`, like
  `msSidebar` and `msEditorConfirmations`; the cost is that a creator re-hides it on a new device.
  A `CreatorPreferences` column was the alternative and is the follow-up if that turns out to
  matter. Phone = the editor's one breakpoint, 767.98 px, read once on load. The "×" is our own
  fixed button beside Chatwoot's bubble (the SDK has no dismiss), removed with
  `$chatwoot.toggleBubbleVisibility('hide')`. The editor keeps `showUnreadMessagesDialog: false`
  with the bubble shown: the widget still never speaks over the work.
